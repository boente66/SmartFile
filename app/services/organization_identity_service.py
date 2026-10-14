from dataclasses import asdict, fields, replace
from datetime import datetime, timezone
from io import BytesIO
import base64
import json
import re
from uuid import UUID

from PIL import Image, UnidentifiedImageError

from app.models.corporate_identity import CorporateIdentity
from app.repositories.organization_identity_repository import OrganizationIdentityRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.services.audit_service import AuditService
from app.services.smartfile_instance_service import SmartFileInstanceService


class OrganizationIdentityService:
    """Identidade declarada, institucional e controlada; não aceita estilos/código externos."""
    EDITABLE = {'display_name', 'legal_name', 'cnpj', 'address', 'unit', 'privacy_contact',
                'privacy_notice', 'accent_color', 'header_color', 'logo', 'institutional_image',
                'show_legal_details_on_receipts'}
    MAX_IMAGE_INPUT = 5 * 1024 * 1024
    MAX_PAYLOAD = 900 * 1024

    def __init__(self, database, context=None):
        self.database, self.context = database, context
        self.repository = OrganizationIdentityRepository(database=database)
        self.organizations = OrganizationRepository(database=database)
        self.members = OrganizationMemberRepository(database=database)
        self.instances = SmartFileInstanceService(database, context)
        self.audit = AuditService(database, context)

    def _organization(self, organization_id):
        organization = self.organizations.find_by_id(organization_id)
        if organization is None or organization.status != 'ACTIVE':
            raise PermissionError('Organização indisponível.')
        return organization

    def _admin(self, organization_id):
        organization = self._organization(organization_id)
        if organization.profile_code != 'BUSINESS':
            raise PermissionError('Modo Design disponível somente para organizações BUSINESS.')
        if self.context is not None:
            if not self.context.is_authenticated():
                raise PermissionError('Entre no SmartFile para continuar.')
            member = self.members.find(organization_id, self.context.current_user.id)
            if member is None or member.status != 'ACTIVE' or member.role not in {'OWNER', 'ADMIN'}:
                raise PermissionError('Somente OWNER/ADMIN pode alterar a identidade institucional.')
            if organization_id != getattr(self.context.active_organization, 'id', None):
                raise PermissionError('Ative a organização antes de alterar sua identidade.')
        return organization

    def get(self, organization_id):
        organization = self._organization(organization_id)
        if self.context is not None:
            self.context.require_organization_permission(organization_id, 'organization.view')
        if organization.profile_code != 'BUSINESS':
            return CorporateIdentity()
        try:
            values = self.repository.get(organization_id)
            return self._validate_payload(values) if values else CorporateIdentity(organization_uuid=organization.public_uuid)
        except (ValueError, TypeError, KeyError):
            return CorporateIdentity(organization_uuid=organization.public_uuid)

    @staticmethod
    def normalize_cnpj(value):
        value = re.sub(r'[.\s/-]', '', value.upper())
        if not value:
            return ''
        if not re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', value) or len(set(value)) == 1:
            raise ValueError('CNPJ inválido: informe 12 caracteres e dois dígitos verificadores.')
        base = value[:12]
        for weights in ((5,4,3,2,9,8,7,6,5,4,3,2), (6,5,4,3,2,9,8,7,6,5,4,3,2)):
            remainder = sum((ord(character)-48)*weight for character, weight in zip(base, weights)) % 11
            base += str(0 if remainder < 2 else 11-remainder)
        if base != value:
            raise ValueError('Os dígitos verificadores do CNPJ não conferem.')
        return value

    @classmethod
    def normalize_image(cls, data, kind='logo'):
        if kind not in {'logo', 'institutional_image'}:
            raise ValueError('Tipo de imagem inválido.')
        if not data or len(data) > cls.MAX_IMAGE_INPUT:
            raise ValueError('Use imagem PNG, JPEG ou WEBP de até 5 MB.')
        try:
            with Image.open(BytesIO(data)) as image:
                if image.format not in {'PNG', 'JPEG', 'WEBP'} or max(image.size) > 4096:
                    raise ValueError('Formato inválido ou imagem maior que 4096 pixels.')
                image.verify()
            with Image.open(BytesIO(data)) as source:
                image = source.convert('RGBA' if kind == 'logo' else 'RGB')
                image.thumbnail((400, 400) if kind == 'logo' else (960, 540))
                try:
                    while True:
                        output = BytesIO()
                        image.save(output, format='PNG' if kind == 'logo' else 'JPEG', **({} if kind == 'logo' else {'quality': 80}))
                        encoded = output.getvalue()
                        if len(encoded) <= (180*1024 if kind == 'logo' else 400*1024):
                            return base64.b64encode(encoded).decode('ascii')
                        image.thumbnail((max(1, int(image.width*.8)), max(1, int(image.height*.8))))
                finally:
                    image.close()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError('Não foi possível validar a imagem institucional.') from exc

    def preview(self, organization_id, values):
        organization = self._admin(organization_id)
        return self._editable(values, organization.public_uuid)

    def _editable(self, values, organization_uuid):
        if not isinstance(values, dict) or not set(values).issubset(self.EDITABLE):
            raise ValueError('Campo institucional não permitido.')
        clean = dict(values)
        for key in self.EDITABLE - {'logo','institutional_image','show_legal_details_on_receipts'}:
            value = clean.get(key, '#2563eb' if key=='accent_color' else '#0f172a' if key=='header_color' else '')
            if not isinstance(value, str) or len(value) > (4000 if key=='privacy_notice' else 500 if key=='address' else 180):
                raise ValueError(f'Campo institucional inválido: {key}.')
            if any(ord(c)<32 and c not in '\n\t' for c in value):
                raise ValueError('Caracteres de controle não são permitidos.')
            clean[key] = value.strip()
        clean['cnpj'] = self.normalize_cnpj(clean.get('cnpj',''))
        if clean['cnpj'] and not clean['legal_name']:
            raise ValueError('Informe a razão social ao cadastrar um CNPJ.')
        for key in ('accent_color','header_color'):
            clean[key] = CorporateIdentity.color(clean[key])
        for key in ('logo','institutional_image'):
            encoded = clean.get(key, '')
            if not isinstance(encoded, str) or len(encoded) > 600*1024:
                raise ValueError('Imagem institucional excede o limite.')
            if encoded:
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except ValueError as exc:
                    raise ValueError('Imagem institucional inválida.') from exc
                try:
                    with Image.open(BytesIO(raw)) as header:
                        expected = 'PNG' if key == 'logo' else 'JPEG'
                        bounds = (400,400) if key == 'logo' else (960,540)
                        if header.format != expected or header.width > bounds[0] or header.height > bounds[1]:
                            raise ValueError('A imagem deve ser normalizada antes de salvar.')
                        header.verify()
                except (OSError, UnidentifiedImageError) as exc:
                    raise ValueError('Imagem institucional inválida.') from exc
            clean[key] = encoded
        legal = clean.get('show_legal_details_on_receipts', False)
        if not isinstance(legal, bool):
            raise ValueError('Opção de comprovante inválida.')
        clean['show_legal_details_on_receipts'] = legal
        return CorporateIdentity(organization_uuid=organization_uuid, **clean)

    def save(self, organization_id, values):
        organization = self._admin(organization_id)
        binding = self.repository.get(organization_id, 'corporate_identity_source')
        if binding:
            raise PermissionError('Esta instalação utiliza uma fonte institucional. Edite na instalação de origem.')
        preview = self._editable(values, organization.public_uuid)
        current = self.get(organization_id)
        local = self.instances.local(organization_id)
        identity = replace(preview, revision=current.revision+1,
            updated_at=datetime.now(timezone.utc).isoformat(),
            editor_username=getattr(self.context.current_user,'username','SYSTEM') if self.context else 'SYSTEM',
            authority_instance_id=local.instance_id)
        with self.database.transaction():
            self.repository.save(organization_id, asdict(identity))
            self.audit.record('CORPORATE_DESIGN_UPDATED', organization_id=organization_id,
                target_type='organization', target_id=organization_id,
                details={'revision':identity.revision, 'fields':sorted(values)})
        return identity

    def _validate_payload(self, values):
        if not isinstance(values, dict) or set(values) != {field.name for field in fields(CorporateIdentity)}:
            raise ValueError('Formato de identidade institucional inválido.')
        UUID(values['organization_uuid'])
        if type(values['revision']) is not int or values['revision'] < 0:
            raise ValueError('Revisão institucional inválida.')
        editable = self._editable({k:v for k,v in values.items() if k in self.EDITABLE}, values['organization_uuid'])
        for key in ('updated_at','editor_username','authority_instance_id'):
            if not isinstance(values[key],str) or len(values[key])>180:
                raise ValueError('Origem institucional inválida.')
        return replace(editable, **{key:values[key] for key in ('revision','updated_at','editor_username','authority_instance_id')})

    def source(self, organization_id):
        return self.repository.get(organization_id, 'corporate_identity_source')

    def package_for_peer(self, requester_instance_id):
        peer = self.instances.repository.find_by_instance_id(requester_instance_id)
        if peer is None or peer.is_local or not peer.enabled:
            raise PermissionError('Instalação não autorizada.')
        organization = self._organization(peer.organization_id)
        if organization.profile_code != 'BUSINESS':
            raise PermissionError('Identidade institucional indisponível.')
        local = self.instances.local(organization.id)
        return {'instance_id':local.instance_id, 'identity':asdict(self.get(organization.id))}

    def bind_source(self, organization_id, peer_instance_id, package):
        self._admin(organization_id)
        peer = self.instances.repository.find_by_instance_id(peer_instance_id)
        if peer is None or peer.is_local or not peer.enabled or peer.organization_id != organization_id:
            raise PermissionError('Fonte não pertence à organização autorizada.')
        identity = self._validate_package(peer_instance_id, package)
        current = self.get(organization_id)
        if current.cnpj and identity.cnpj != current.cnpj:
            raise PermissionError('O CNPJ da fonte difere do cadastro desta organização.')
        with self.database.transaction():
            self.repository.save(organization_id, {'instance_id':peer_instance_id,'organization_uuid':identity.organization_uuid}, 'corporate_identity_source')
            self.repository.bind_public_identity(organization_id, identity.organization_uuid)
            self.repository.save(organization_id, asdict(identity))
            self.audit.record('CORPORATE_IDENTITY_SOURCE_BOUND', organization_id=organization_id,
                target_type='organization', target_id=organization_id,
                details={'source_instance_id':peer_instance_id,'revision':identity.revision})
        return identity

    def detach_source(self, organization_id):
        self._admin(organization_id)
        with self.database.transaction():
            self.repository.save(organization_id, None, 'corporate_identity_source')
            self.audit.record('CORPORATE_IDENTITY_SOURCE_DETACHED', organization_id=organization_id,
                target_type='organization', target_id=organization_id)

    def _validate_package(self, peer_id, package):
        if not isinstance(package,dict) or set(package) != {'instance_id','identity'} or package['instance_id'] != peer_id:
            raise PermissionError('A origem do pacote institucional não confere.')
        if len(json.dumps(package).encode()) > self.MAX_PAYLOAD:
            raise ValueError('Pacote institucional excede o limite.')
        identity = self._validate_payload(package['identity'])
        if identity.authority_instance_id != peer_id or identity.revision < 1:
            raise PermissionError('A instalação selecionada não é a fonte autoritativa desta identidade.')
        return identity

    def synchronize(self, organization_id, *, client=None):
        if self._organization(organization_id).profile_code != 'BUSINESS':
            return CorporateIdentity()
        binding = self.source(organization_id)
        if not binding:
            return self.get(organization_id)
        peer = self.instances.repository.find_by_instance_id(binding['instance_id'])
        if peer is None or not peer.enabled or peer.is_local or peer.organization_id != organization_id:
            raise PermissionError('Fonte institucional não está autorizada nesta organização.')
        from app.delivery.delivery_http_client import DeliveryHttpClient
        local = self.instances.local(organization_id)
        client = client or DeliveryHttpClient(timeout=5)
        package = client.organization_identity(peer.current_ip, peer.http_port, local.instance_id)
        identity = self._validate_package(peer.instance_id, package)
        if identity.organization_uuid != binding['organization_uuid']:
            raise PermissionError('A organização da fonte mudou; é necessário um novo vínculo administrativo.')
        current = self.get(organization_id)
        if identity.revision < current.revision:
            raise PermissionError('A fonte apresentou uma revisão institucional antiga.')
        if identity.revision == current.revision:
            if identity != current:
                raise PermissionError('Revisões iguais possuem conteúdo divergente.')
            return current
        with self.database.transaction():
            if self.context is not None:
                self.context.require_organization_permission(organization_id,'organization.view')
                actor=self.audit.current_actor()
                if actor is not None and actor.username != getattr(self.context.current_user,'username',None):
                    raise PermissionError('A sessão que iniciou a sincronização não está mais ativa.')
            self.repository.save(organization_id, asdict(identity))
            self.audit.record('CORPORATE_IDENTITY_SYNCHRONIZED', organization_id=organization_id,
                target_type='organization', target_id=organization_id,
                details={'source_instance_id':peer.instance_id,'revision':identity.revision})
        return identity
