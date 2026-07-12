from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem, QVBoxLayout


class PDFSignatureValidationDialog(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Validação de assinaturas digitais")
        self.resize(900, 420)
        layout = QVBoxLayout(self)
        table = QTableWidget(len(results), 7)
        table.setHorizontalHeaderLabels(
            ["Campo", "Estado", "Assinante", "Emissor", "Integridade", "Confiança", "Perfil"]
        )
        for row, result in enumerate(results):
            values = (
                result.field_name, result.state, result.signer_name, result.issuer,
                "Íntegro" if result.integrity_ok else "Falhou",
                "Confiável" if result.trusted else "Não confiável", result.pades_profile,
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
