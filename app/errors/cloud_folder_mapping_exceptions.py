class CloudFolderMappingError(RuntimeError):
    """Falha de domínio ao associar uma pasta lógica a uma pasta remota."""


class CloudFolderMappingConflictError(CloudFolderMappingError):
    pass


class InvalidRemoteFolderError(CloudFolderMappingError):
    pass
