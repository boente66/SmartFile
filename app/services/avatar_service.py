from pathlib import Path
from uuid import uuid4

from PIL import Image

from app.errors.auth_exceptions import AvatarError


class AvatarService:
    EXTENSIONS={".png",".jpg",".jpeg",".webp"}
    MAX_SIZE=5*1024*1024

    def __init__(self, database):
        self.directory=database.data_dir / "avatars"
        self.directory.mkdir(parents=True,exist_ok=True)

    def store(self, source: str | None) -> str | None:
        if not source: return None
        path=Path(source).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in self.EXTENSIONS: raise AvatarError("Selecione uma imagem PNG, JPG ou WEBP válida.")
        if path.stat().st_size > self.MAX_SIZE: raise AvatarError("O avatar deve possuir no máximo 5 MB.")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                if image.width < 64 or image.height < 64: raise AvatarError("O avatar deve possuir pelo menos 64 x 64 pixels.")
                target=self.directory / f"{uuid4().hex}.png"
                image.convert("RGBA").save(target,"PNG")
                return str(target)
        except AvatarError: raise
        except Exception as exc: raise AvatarError("Não foi possível validar o avatar.") from exc

    @staticmethod
    def initials(name: str) -> str:
        parts=[part for part in name.split() if part]
        return "".join(part[0].upper() for part in parts[:2]) or "SF"
