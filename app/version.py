"""Versão pública do SmartFile e conversão para formatos de distribuição."""

__version__ = "0.9.0-beta.1"


def debian_version() -> str:
    """Retorna uma versão equivalente aceita pela ordenação de pacotes Debian."""

    return __version__.replace("-beta.", "~beta")
