from app.errors.auth_exceptions import TemplateCreationError
from app.services.folder_service import FolderService


class FolderTemplateService:
    TEMPLATES = {
        "PERSONAL": ("Documentos pessoais", "Contas", "Garantias", "Saúde", "Imposto de Renda", "Comprovantes"),
        "STUDENT": ("Disciplinas", "Trabalhos", "Projetos", "TCC", "Certificados", "Livros e materiais"),
        "BUSINESS": ("Financeiro", "Fiscal", "Recursos Humanos", "Contratos", "Clientes", "Fornecedores", "Administrativo", "Projetos"),
        "EMPTY": (),
    }

    def __init__(self, folder_service: FolderService):
        self.folder_service = folder_service

    def create_template_folders(self, organization_id: int, template_code: str):
        code = template_code.upper()
        if code not in self.TEMPLATES:
            raise TemplateCreationError("Modelo de pastas inválido.")
        try:
            existing = {folder.name.casefold() for folder in self.folder_service.list_folders(organization_id)}
            return [
                self.folder_service.create(organization_id, name)
                for name in self.TEMPLATES[code]
                if name.casefold() not in existing
            ]
        except Exception as exc:
            raise TemplateCreationError("Não foi possível criar as pastas iniciais.") from exc
