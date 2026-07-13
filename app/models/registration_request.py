from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegistrationRequest:
    display_name: str
    username: str
    password: str
    password_confirmation: str
    template_code: str
    email: str | None = None
    phone: str | None = None
