from app.controllers.convert_controller import ConvertController
from app.controllers.document_controller import DocumentController
from app.controllers.pdf_controller import PDFController
from app.controllers.scan_controller import ScanController


class AppController:
    """
    Controller principal da aplicação.
    """

    def __init__(self, main_view):
        self.main_view = main_view
        self.workspace = main_view.workspace

        # Controllers ainda NÃO ativos
        self.convert_controller = None
        self.pdf_controller = None
        self.scan_controller = None
        self.document_controller = None

    def start(self):
        """
        Inicializa funcionalidades do sistema.
        Chamado após UI estar pronta.
        """
        # Criar controllers
        self.convert_controller = ConvertController(self.workspace, self.main_view)
        self.pdf_controller = PDFController(self.workspace)
        self.scan_controller = ScanController(self.workspace)
        self.document_controller = DocumentController(
            self.workspace,
            self.main_view,
            convert_controller=self.convert_controller,
            pdf_controller=self.pdf_controller,
        )

        # Conectar navegação
        self.main_view.sidebar.tool_selected.connect(self.on_tool_selected)

        # Tela inicial
        self.document_controller.activate()
        self.main_view.sidebar.set_active_tool("documents")

    def on_tool_selected(self, tool_name: str):
        if tool_name == "converter":
            self.convert_controller.activate()
        elif tool_name == "pdf":
            self.pdf_controller.activate()
        elif tool_name == "scanner":
            self.scan_controller.activate()
        elif tool_name == "documents":
            self.document_controller.activate()
