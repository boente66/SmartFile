from dataclasses import dataclass


@dataclass(slots=True)
class PasswordRecoveryCodeEntity:
    """Representa um código de recuperação sem armazenar o segredo em texto."""

    id: int | None = None
    user_id: int = 0
    code_lookup: str = ""
    code_hash: str = ""
    created_at: str = ""
    expires_at: str = ""
    used_at: str | None = None
