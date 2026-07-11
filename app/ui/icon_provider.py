from pathlib import Path

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QAbstractButton


class IconProvider:
    """Ponto único de acesso aos ícones SVG do SmartFile."""

    _icons_dir = Path(__file__).resolve().parents[2] / "assets" / "icons"
    DEFAULT_SIZE = QSize(18, 18)

    @classmethod
    def icon(cls, name: str) -> QIcon:
        path = cls._icons_dir / f"{name}.svg"
        if not path.is_file():
            raise ValueError(f"Ícone não encontrado: {name}")
        return QIcon(str(path))

    @classmethod
    def apply(
        cls,
        button: QAbstractButton,
        name: str,
        size: QSize | None = None,
    ) -> None:
        button.setIcon(cls.icon(name))
        button.setIconSize(size or cls.DEFAULT_SIZE)
