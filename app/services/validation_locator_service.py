import ipaddress
import re
from urllib.parse import urlsplit


class ValidationLocatorService:
    TOKEN = re.compile(r"SFV1-[A-Za-z0-9_-]{43}")
    CODE = re.compile(r"SFV[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{16}")
    PREFIX = "smartfile:verify:v1:"

    @classmethod
    def validate_token(cls, value):
        if not cls.TOKEN.fullmatch(value):
            raise ValueError("INVALID_TOKEN: token de validação inválido.")
        return value

    @classmethod
    def normalize_code(cls, value):
        code = re.sub(r"[\s-]", "", value).upper()
        if not cls.CODE.fullmatch(code):
            raise ValueError("Código de validação inválido.")
        return code

    @staticmethod
    def validate_base_url(value):
        if not value:
            return None
        if len(value) > 1000 or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
            raise ValueError("Base de validação inválida.")
        url = urlsplit(value)
        host = (url.hostname or "").lower().rstrip(".")
        if url.scheme != "https" or not host or url.username or url.password or url.query or url.fragment:
            raise ValueError("Use uma base HTTPS sem credenciais, query ou fragmento.")
        if host == "localhost" or host.endswith((".localhost", ".local")) or "." not in host:
            raise ValueError("A base de validação deve ser pública; localhost não é permitido.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            # Reject alternative numeric loopback forms too.
            if re.fullmatch(r"[0-9.]+", host) or host.startswith("0x"):
                raise ValueError("Endereço de validação inválido.")
        else:
            if not address.is_global:
                raise ValueError("Endereço local/privado não é permitido.")
        try:
            url.port
        except ValueError as exc:
            raise ValueError("Porta da base inválida.") from exc
        if any(part in {".", ".."} for part in url.path.split("/")) or "%" in url.netloc:
            raise ValueError("Base de validação inválida.")
        return value.rstrip("/")

    @classmethod
    def build_payload(cls, record):
        token = cls.validate_token(record.public_token)
        base = cls.validate_base_url(record.base_url_snapshot)
        return f"{base}/verify/{token}" if base else cls.PREFIX + token

    @classmethod
    def parse(cls, value):
        value = value.strip()
        if value.startswith("smartfile:"):
            if not value.startswith(cls.PREFIX):
                raise ValueError("UNSUPPORTED_PAYLOAD: versão ou formato do QR não suportado.")
            return "TOKEN", cls.validate_token(value[len(cls.PREFIX):])
        if value.startswith("https://"):
            url = urlsplit(value)
            if url.query or url.fragment:
                raise ValueError("Payload de validação inválido.")
            base, separator, token = value.rpartition("/verify/")
            if not separator:
                raise ValueError("URL de validação inválida.")
            cls.validate_base_url(base)
            return "TOKEN", cls.validate_token(token)
        if value.startswith("SFV1-"):
            return "TOKEN", cls.validate_token(value)
        return "CODE", cls.normalize_code(value)
