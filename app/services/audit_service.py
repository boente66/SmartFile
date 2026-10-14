from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict
from datetime import datetime, timezone
import json
import re
from uuid import uuid4
from types import SimpleNamespace

from app.entities.audit_log_entity import AuditLogEntity
from app.models.audit_actor import AuditActor
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.smartfile_instance_service import SmartFileInstanceService

_ACTOR = ContextVar('smartfile_audit_actor', default=None)


class AuditService:
    def __init__(self, database, context=None):
        self.database = database
        self.context = context
        self.repository = AuditLogRepository(database=database)

    @staticmethod
    def current_actor():
        return _ACTOR.get()

    @staticmethod
    @contextmanager
    def bind(actor):
        token = _ACTOR.set(actor)
        try:
            yield
        finally:
            _ACTOR.reset(token)

    def capture(self, organization_id=None, *, user_id=None, instance_id=None):
        bound = self.current_actor()
        if bound is not None and (organization_id is None or bound.organization_id == organization_id) and user_id is None:
            return bound
        if organization_id is None:
            organization_id = getattr(getattr(self.context, 'active_organization', None), 'id', None)
        user = getattr(self.context, 'current_user', None)
        if user_id is not None and getattr(user, 'id', None) != user_id:
            user = None
        if user_id is None and user is not None:
            user_id = user.id
        organization = self.database.fetch_one('SELECT name,public_uuid FROM organizations WHERE id=?', (organization_id,))
        row = self.database.fetch_one('SELECT username,display_name FROM users WHERE id=?', (user_id,)) if user_id else None
        if instance_id is None and organization is not None:
            instance_context = (self.context or SimpleNamespace(current_user=SimpleNamespace(id=user_id))) if row else None
            instance_id = SmartFileInstanceService(self.database, instance_context).local(organization_id).instance_id
        return AuditActor(organization_id, organization['name'] if organization else None,
                          organization['public_uuid'] if organization else None, user_id if row else None,
                          row['username'] if row else getattr(user, 'username', None) or 'SYSTEM',
                          row['display_name'] if row else getattr(user, 'display_name', None), instance_id)

    def record(self, action, *, user_id=None, organization_id=None, target_type=None,
               target_id=None, description=None, actor=None, document=None,
               sha256_before=None, sha256_after=None, details=None, source_type=None):
        bound = actor or self.current_actor()
        if organization_id is None:
            organization_id = bound.organization_id if bound else getattr(getattr(self.context, 'active_organization', None), 'id', None)
        scope=self.current_actor()
        if scope is not None and scope.organization_id != organization_id:
            raise PermissionError('O worker foi iniciado em outra organização.')
        if bound is not None and bound.organization_id != organization_id:
            raise PermissionError('O contexto de auditoria pertence a outra organização.')
        actor = bound or self.capture(organization_id, user_id=user_id)
        for checksum in (sha256_before, sha256_after):
            if checksum is not None and re.fullmatch(r'[a-f0-9]{64}', checksum) is None:
                raise ValueError('SHA-256 de auditoria inválido.')
        description = self._redact(description)
        return self.repository.create(AuditLogEntity(
            user_id=actor.user_id, organization_id=organization_id,
            action=action.upper(), target_type=target_type, target_id=target_id,
            description=description, created_at=datetime.now(timezone.utc).isoformat(),
            event_uuid=str(uuid4()), actor_username=actor.username, actor_name=actor.display_name,
            organization_name=actor.organization_name, organization_uuid=actor.organization_uuid,
            instance_id=actor.instance_id, document_uuid=getattr(document, 'public_uuid', None),
            document_name=getattr(document, 'name', None),
            source_type=source_type or getattr(document, 'source_type', None),
            sha256_before=sha256_before, sha256_after=sha256_after,
            details_json=json.dumps(self._clean_details(details), ensure_ascii=False) if details is not None else None,
        ))

    @classmethod
    def _clean_details(cls,value):
        if isinstance(value,dict):
            return {key:('[REDACTED]' if re.search(r'(?i)(password|senha|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|credentials?)',str(key)) else cls._clean_details(item)) for key,item in value.items()}
        if isinstance(value,(tuple,list)):
            return [cls._clean_details(item) for item in value]
        return cls._redact(value) if isinstance(value,str) else value

    @staticmethod
    def _redact(value):
        if value is None:
            return None
        return re.sub(r'(?i)(access[_-]?token|refresh[_-]?token|client[_-]?secret|password|senha|authorization)\s*[:=]\s*\S+', r'\1=[REDACTED]', str(value))[:2000]

    def list_for_organization(self, organization_id, limit=100, **filters):
        if self.context is not None:
            self.context.require_organization_permission(organization_id, 'audit.view')
        self._validate_dates(filters)
        return self.repository.find_by_organization(organization_id, limit, **filters)

    def for_document(self, organization_id, document_id):
        if self.context is not None:
            self.context.require_organization_permission(organization_id, 'document.view')
        # target_id is deliberately not a document FK: deletion retains this lookup.
        from app.repositories.document_repository import DocumentRepository
        document = DocumentRepository(database=self.database).find_by_id(document_id, organization_id)
        if document and document.public_uuid:
            return self.repository.find_by_organization(organization_id, 5000, document_uuid=document.public_uuid)
        return self.repository.find_by_organization(organization_id, 5000, document_id=document_id)

    @staticmethod
    def _validate_dates(filters):
        for field in ('from_date', 'to_date'):
            if filters.get(field):
                datetime.fromisoformat(filters[field])
        if filters.get('from_date') and filters.get('to_date'):
            if datetime.fromisoformat(filters['from_date']) > datetime.fromisoformat(filters['to_date']):
                raise ValueError('O início do período deve anteceder o fim.')

    @staticmethod
    def serialize_actor(actor):
        return json.dumps(asdict(actor), ensure_ascii=False) if actor else None

    @staticmethod
    def deserialize_actor(value):
        return AuditActor(**json.loads(value)) if value else None
