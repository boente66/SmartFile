from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout
from app.views.widgets.pdf_signature_placement_widget import PDFSignaturePlacementWidget
from app.views.widgets.qr_placement_overlay import QrPlacementOverlay
from app.views.widgets.signature_qr_options import SignatureQrOptions


def configure_reposition(options, location):
    options.position.setCurrentIndex(2)
    options.visible.setChecked(True)
    options.visible.setEnabled(False)
    options.page.setValue(location.page_number)
    options.page.setEnabled(False)
    options.size.setValue(location.rect[2] - location.rect[0])
    options.x.setValue(location.rect[0]); options.y.setValue(location.rect[1])


class QrRepositionDialog(QDialog):
    def __init__(self, preview, location, output, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Reposicionar QR — salvar nova cópia')
        self.resize(900, 700)
        root = QHBoxLayout(self)
        self.placement = PDFSignaturePlacementWidget(preview, *location.page_size)
        root.addWidget(self.placement, 1)
        fields = QVBoxLayout(); root.addLayout(fields)
        self.options = SignatureQrOptions(location.page_number)
        configure_reposition(self.options, location)
        fields.addWidget(self.options)
        self.overlay = QrPlacementOverlay(self.placement, self.options)
        self.overlay.unlock()
        self.output = QLineEdit(str(output)); fields.addWidget(self.output)
        browse = QPushButton('Salvar como…'); fields.addWidget(browse)
        browse.clicked.connect(self._choose_output)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        fields.addWidget(buttons)

    def _choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Salvar nova cópia', self.output.text(), 'PDF (*.pdf)')
        if path:
            self.output.setText(path)
