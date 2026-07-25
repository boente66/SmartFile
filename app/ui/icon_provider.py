from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QAbstractButton

from app.system.resources import resource_path


class IconProvider:
    """Ponto único de acesso aos ícones SVG do SmartFile."""

    _icons_dir = resource_path("assets/icons")
    DEFAULT_SIZE = QSize(18, 18)

    @classmethod
    def icon(cls, name: str) -> QIcon:
        path = cls._icon_path(name)
        return QIcon(str(path))

    @classmethod
    def colored_icon(
        cls, name: str, color: str, size: QSize | None = None,
    ) -> QIcon:
        """Renderiza um SVG com cor de estado sem duplicar arquivos de ícone."""

        path = cls._icon_path(name)
        svg = path.read_text(encoding="utf-8")
        svg = svg.replace("currentColor", color)
        svg = svg.replace('stroke="#cbd5e1"', f'stroke="{color}"')
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        target = size or cls.DEFAULT_SIZE
        pixmap = QPixmap(target)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    @classmethod
    def _icon_path(cls, name: str):
        path = cls._icons_dir / f"{name}.svg"
        if not path.is_file():
            raise ValueError(f"Ícone não encontrado: {name}")
        return path

    @classmethod
    def apply(
        cls,
        button: QAbstractButton,
        name: str,
        size: QSize | None = None,
        color: str | None = None,
    ) -> None:
        target = size or cls.DEFAULT_SIZE
        button.setIcon(
            cls.colored_icon(name, color, target)
            if color else cls.icon(name)
        )
        button.setIconSize(target)
