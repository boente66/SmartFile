"""Exceções de domínio do mecanismo de backup."""


class BackupError(Exception):
    """Falha geral ao criar ou validar um backup."""


class BackupPermissionError(BackupError):
    """O usuário atual não pode executar backups administrativos."""


class InvalidBackupDestinationError(BackupError):
    """O destino informado para o backup não é seguro ou válido."""


class BackupStorageError(BackupError):
    """Falha ao ler dados ou gravar o arquivo de backup."""
