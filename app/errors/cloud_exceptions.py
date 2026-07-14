class CloudOAuthError(RuntimeError):
    """Erro de domínio no fluxo de autorização de nuvem."""


class CloudConfigurationMissingError(CloudOAuthError):
    pass


class CloudConfigurationInvalidError(CloudOAuthError):
    pass


class CloudAuthorizationCancelledError(CloudOAuthError):
    pass


class CloudAuthorizationDeniedError(CloudOAuthError):
    pass


class CloudAuthorizationTimeoutError(CloudOAuthError):
    pass


class CloudTokenExpiredError(CloudOAuthError):
    pass


class CloudPermissionError(CloudOAuthError):
    pass


class CloudTokenStoreError(CloudOAuthError):
    pass
