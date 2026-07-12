class DatabaseError(RuntimeError):
    """Falha ao abrir, migrar ou operar o banco de dados."""


class RepositoryError(RuntimeError):
    """Falha de persistência em um repository."""


class DuplicateDocumentError(ValueError):
    """Documento já cadastrado, identificado pelo checksum SHA-256."""


class StorageError(RuntimeError):
    """Falha ao manipular o armazenamento interno."""


class InvalidDocumentError(ValueError):
    """Arquivo de entrada inválido para cadastro documental."""
