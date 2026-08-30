class MulticloudError(RuntimeError):
    """Erro de domínio do espelho lógico multicloud."""


class RemoteMountError(MulticloudError):
    pass


class ReconciliationAuthorizationError(MulticloudError):
    pass


class ReplicaConflictError(MulticloudError):
    pass
