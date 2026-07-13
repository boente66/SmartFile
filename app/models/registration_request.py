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
    organization_name: str = "Minha Organização"
    organization_description: str | None = None
    organization_icon: str = "organization"
    organization_color: str = "#2563eb"
    avatar_path: str | None = None
