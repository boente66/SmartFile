class DeliveryError(Exception):
    """Falha de domínio da entrega documental."""


class DeliveryPermissionError(DeliveryError):
    pass


class DeliveryIntegrityError(DeliveryError):
    pass


class DeliveryNetworkError(DeliveryError):
    pass


class DeliveryValidationError(DeliveryError):
    pass


class DeliveryNotFoundError(DeliveryError):
    pass
