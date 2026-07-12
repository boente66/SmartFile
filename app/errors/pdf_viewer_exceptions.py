class PDFViewerError(RuntimeError):
    """Erro de domínio do visualizador de PDF."""


class PDFPasswordRequiredError(PDFViewerError):
    """O documento exige senha para leitura."""


class PDFInvalidPasswordError(PDFViewerError):
    """A senha informada não desbloqueou o documento."""


class InvalidPDFError(PDFViewerError):
    """Arquivo inexistente, inválido ou incompatível com PDF."""
