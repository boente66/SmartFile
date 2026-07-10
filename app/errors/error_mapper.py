from app.errors.error_codes import ErrorCode


ERROR_MESSAGES = {
    ErrorCode.FILE_NOT_FOUND: "Arquivo não encontrado.",
    ErrorCode.INVALID_OUTPUT_DIR: "Diretório de saída inválido.",
    ErrorCode.UNSUPPORTED_FORMAT: "Formato não suportado.",

    ErrorCode.SCANNER_NOT_FOUND: "Nenhum scanner foi encontrado.",
    ErrorCode.SCANNER_BUSY: "O scanner está ocupado.",
    ErrorCode.SCANNER_NO_PAPER: "O scanner está sem papel.",

    ErrorCode.PDF_INVALID: "O arquivo PDF é inválido.",
    ErrorCode.PDF_EMPTY: "O PDF não possui páginas.",

    ErrorCode.CONVERSION_FAILED: "Falha ao converter o arquivo.",
    ErrorCode.UNKNOWN: "Erro inesperado."
}


def get_user_message(error) -> str:
    return ERROR_MESSAGES.get(error.code, ERROR_MESSAGES[ErrorCode.UNKNOWN])