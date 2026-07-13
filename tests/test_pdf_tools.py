from pathlib import Path

import fitz
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication
from pypdf import PdfReader

from app.controllers.pdf_controller import PDFController
from app.services.pdf_edit_service import PDFEditService
from app.views.pdf_view import PDFView
from app.views.workspace_view import WorkspaceView

_APPLICATION = None


def _app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _pdf(path: Path, pages: int = 3) -> Path:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=300, height=500)
        page.insert_text((30, 50), f"Página {index + 1}")
    document.save(path); document.close()
    return path


def test_pdf_tools_view_has_model_actions_and_preserves_page_ids():
    _app()
    view = PDFView()
    view.load_pdf("/tmp/modelo.pdf")
    pixmaps = [QPixmap(100, 140) for _ in range(3)]
    for pixmap in pixmaps:
        pixmap.fill(Qt.GlobalColor.white)
    view.show_thumbnails(pixmaps, [7, 3, 9])

    labels = {button.text() for button in view.toolbar_buttons}
    assert {"Voltar", "Adicionar", "Remover", "Mover", "Girar", "Extrair", "Dividir", "Mesclar", "Salvar"} <= labels
    assert [view.page_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(3)] == [7, 3, 9]
    assert all(not button.icon().isNull() for button in view.toolbar_buttons)
    assert len(view.action_buttons) == 7
    view.close()


def test_compose_and_split_apply_order_and_rotation(tmp_path: Path):
    source = _pdf(tmp_path / "source.pdf")
    output = tmp_path / "composed.pdf"

    PDFEditService.compose_pages(source, output, [2, 0], {2: 90})

    reader = PdfReader(output)
    assert len(reader.pages) == 2
    assert "Página 3" in reader.pages[0].extract_text()
    assert reader.pages[0].rotation == 90

    outputs = PDFEditService.split_pdf(source, tmp_path / "split", [1, 2], {1: 180})
    assert len(outputs) == 2
    assert all(path.is_file() for path in outputs)
    assert PdfReader(outputs[0]).pages[0].rotation == 180


def test_controller_rotation_updates_preview_and_save_state(tmp_path: Path):
    _app()
    workspace = WorkspaceView()
    workspace.register_view("documents", PDFView())
    controller = PDFController(workspace)
    source = _pdf(tmp_path / "source.pdf", pages=2)

    controller.on_open_pdf(str(source))
    controller.on_rotate_pages([0])

    assert controller._pages == [0, 1]
    assert controller._rotations == {0: 90}
    assert controller.view.page_list.count() == 2
    assert controller.view.page_list.item(0).data(Qt.ItemDataRole.UserRole) == 0
    workspace.close()
