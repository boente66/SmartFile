from PyQt6.QtWidgets import QWidget, QStackedLayout


class WorkspaceView(QWidget):
    """
    Área central da aplicação.

    Responsável por exibir um módulo por vez:
    - Documentos
    - Converter
    - PDF Tools
    - Scanner
    """

    def __init__(self):
        super().__init__()

        self._layout = QStackedLayout(self)
        self._views: dict[str, QWidget] = {}
        self._current_view: str | None = None

    # -------------------------
    # API pública
    # -------------------------

    def register_view(self, name: str, view: QWidget):
        """
        Registra uma View no workspace.
        """

        if name in self._views:
            raise ValueError(f"View já registrada: {name}")

        self._views[name] = view
        self._layout.addWidget(view)

    def show_view(self, name: str):
        """
        Exibe a View registrada.
        """

        view = self._views.get(name)

        if view is None:
            raise ValueError(f"View não registrada: {name}")

        self._layout.setCurrentWidget(view)
        self._current_view = name

    # -------------------------
    # Helpers
    # -------------------------

    def current_view(self) -> str | None:
        """
        Retorna o nome da view atual.
        """
        return self._current_view

    def list_views(self) -> list[str]:
        """
        Retorna todas as views registradas.
        """
        return list(self._views.keys())
