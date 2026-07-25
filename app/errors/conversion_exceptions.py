class ConversionError(RuntimeError):
    """Falha de domínio durante uma conversão de arquivo."""


class ConversionCancelledError(ConversionError):
    """Conversão interrompida por solicitação do usuário."""

