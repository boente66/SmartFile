from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)
from PyQt6.QtGui import QPixmap

from app.models.signature_request import SignatureRequest
from app.ui.icon_provider import IconProvider
from app.utils.file_naming import safe_output_path
from app.views.widgets.pdf_signature_placement_widget import PDFSignaturePlacementWidget


class PDFSignatureDialog(QDialog):
    def __init__(self, input_path: Path, page_count: int, current_page: int = 1, preview: QPixmap | None = None, page_size: tuple[float, float] = (595, 842), parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self.page_count = page_count
        self.setWindowTitle("Assinar digitalmente — certificado A1")
        self.resize(980, 680)
        outer = QHBoxLayout(self)
        self.placement = PDFSignaturePlacementWidget(
            preview or QPixmap(), page_size[0], page_size[1]
        )
        outer.addWidget(self.placement, 1)
        form_container = QVBoxLayout()
        outer.addLayout(form_container, 1)
        form = QFormLayout()
        self.certificate_edit = QLineEdit()
        browse = QPushButton("Selecionar…")
        IconProvider.apply(browse, "certificate")
        browse.clicked.connect(self._choose_certificate)
        cert_row = QHBoxLayout(); cert_row.addWidget(self.certificate_edit, 1); cert_row.addWidget(browse)
        form.addRow("Certificado (.pfx/.p12):", cert_row)
        self.password_edit = QLineEdit(); self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Senha:", self.password_edit)
        self.signer_name_edit = QLineEdit(); form.addRow("Nome do assinante:", self.signer_name_edit)
        self.reason_edit = QLineEdit(); form.addRow("Motivo:", self.reason_edit)
        self.location_edit = QLineEdit(); form.addRow("Localização:", self.location_edit)
        self.contact_edit = QLineEdit(); form.addRow("Contato:", self.contact_edit)
        self.profile_combo = QComboBox(); self.profile_combo.addItem("PAdES-B-B")
        form.addRow("Perfil:", self.profile_combo)
        self.timestamp_edit = QLineEdit()
        self.timestamp_edit.setPlaceholderText("Opcional — URL RFC 3161")
        form.addRow("Carimbo de tempo:", self.timestamp_edit)
        self.visible_check = QCheckBox("Criar campo visível")
        self.visible_check.toggled.connect(self._update_visible_fields)
        form.addRow("Aparência:", self.visible_check)
        self.page_spin = QSpinBox(); self.page_spin.setRange(1, max(1, page_count)); self.page_spin.setValue(current_page)
        form.addRow("Página:", self.page_spin)
        self.coordinates = []
        defaults = (40.0, 40.0, 240.0, 110.0)
        for name, default in zip(("X1", "Y1", "X2", "Y2"), defaults):
            spin = QDoubleSpinBox(); spin.setRange(0, 5000); spin.setValue(default)
            self.coordinates.append(spin); form.addRow(f"{name}:", spin)
        self.output_edit = QLineEdit(str(safe_output_path(input_path.with_name(f"{input_path.stem}_assinado.pdf"))))
        output_button = QPushButton("Salvar como…")
        IconProvider.apply(output_button, "save")
        output_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout(); output_row.addWidget(self.output_edit, 1); output_row.addWidget(output_button)
        form.addRow("Saída:", output_row)
        form_container.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form_container.addWidget(buttons)
        self.placement.area_changed.connect(self._set_coordinates)
        self._update_visible_fields(False)

    def build_request(self) -> SignatureRequest:
        x1, y1, x2, y2 = (spin.value() for spin in self.coordinates)
        return SignatureRequest(
            input_path=self.input_path,
            output_path=Path(self.output_edit.text()),
            certificate_path=Path(self.certificate_edit.text()),
            certificate_password=self.password_edit.text(),
            visible=self.visible_check.isChecked(),
            page_number=self.page_spin.value() if self.visible_check.isChecked() else None,
            x1=x1 if self.visible_check.isChecked() else None,
            y1=y1 if self.visible_check.isChecked() else None,
            x2=x2 if self.visible_check.isChecked() else None,
            y2=y2 if self.visible_check.isChecked() else None,
            signer_name=self.signer_name_edit.text().strip() or None,
            reason=self.reason_edit.text().strip() or None,
            location=self.location_edit.text().strip() or None,
            contact_info=self.contact_edit.text().strip() or None,
            timestamp_url=self.timestamp_edit.text().strip() or None,
            pades_profile=self.profile_combo.currentText(),
        )

    def clear_secret(self) -> None:
        self.password_edit.clear()

    def _choose_certificate(self):
        path, _ = QFileDialog.getOpenFileName(self, "Certificado A1", "", "Certificado A1 (*.pfx *.p12)")
        if path: self.certificate_edit.setText(path)

    def _choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar PDF assinado", self.output_edit.text(), "PDF (*.pdf)")
        if path: self.output_edit.setText(path)

    def _update_visible_fields(self, visible: bool):
        self.page_spin.setEnabled(visible)
        for spin in self.coordinates: spin.setEnabled(visible)
        self.placement.setEnabled(visible)

    def _set_coordinates(self, x1, y1, x2, y2):
        for spin, value in zip(self.coordinates, (x1, y1, x2, y2)):
            spin.setValue(value)
