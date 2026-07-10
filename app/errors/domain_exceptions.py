class AppError(Exception):
    def __init__(self, code, detail: str | None = None):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class ScannerError(AppError):
    pass


class PDFError(AppError):
    pass


class ConversionError(AppError):
    pass