class StorageQuotaError(RuntimeError):
    """Falha genérica na cota lógica da organização."""


class StorageQuotaExceededError(StorageQuotaError):
    def __init__(self, used_bytes: int, quota_bytes: int, requested_bytes: int):
        self.used_bytes = used_bytes
        self.quota_bytes = quota_bytes
        self.requested_bytes = requested_bytes
        super().__init__(
            "Limite de armazenamento atingido. "
            f"Esta organização utiliza {format_gb(used_bytes)} de {format_gb(quota_bytes)}. "
            f"O novo documento possui {format_gb(requested_bytes)} e não pode ser adicionado."
        )


class StorageReservationError(StorageQuotaError):
    pass


class StorageRecalculationError(StorageQuotaError):
    pass


class InsufficientLocalDiskSpaceError(StorageQuotaError):
    pass


class ScannerImportError(RuntimeError):
    pass


class CloudStorageLimitError(RuntimeError):
    pass


class ManagedDocumentCreationError(RuntimeError):
    pass


def format_gb(size_bytes: int) -> str:
    value = max(0, int(size_bytes)) / (1024 ** 3)
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " GB"
