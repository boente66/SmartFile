class HandwrittenSignatureError(RuntimeError):
    """Erro base da assinatura manuscrita eletrônica."""


class EmptySignatureError(HandwrittenSignatureError):
    pass


class InvalidSignaturePositionError(HandwrittenSignatureError):
    pass


class InvalidSignaturePageError(HandwrittenSignatureError):
    pass


class SignatureImageError(HandwrittenSignatureError):
    pass


class SignedDocumentWriteError(HandwrittenSignatureError):
    pass


class ExistingDigitalSignatureWarning(HandwrittenSignatureError):
    pass
