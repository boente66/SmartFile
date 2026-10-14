from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
                             QPushButton, QTextBrowser, QComboBox)


class DocumentValidationDialog(QDialog):
    check_requested = pyqtSignal()
    select_file_requested = pyqtSignal()
    read_qr_requested = pyqtSignal()
    open_original_requested = pyqtSignal()
    export_requested = pyqtSignal()
    revoke_requested = pyqtSignal()
    configure_requested = pyqtSignal()
    input_changed = pyqtSignal()
    matching_record_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Validação documental SmartFile")
        self.resize(680, 560)
        layout = QVBoxLayout(self)
        hint = QLabel("O QR localiza um registro. Para verificar a cópia recebida, selecione também seu arquivo. Sem URL pública, a consulta ocorre nesta instalação e organização.")
        hint.setWordWrap(True); layout.addWidget(hint)
        self.locator = QLineEdit(); self.locator.setPlaceholderText("Código SFV, token ou URI/URL do QR")
        self.locator.textChanged.connect(self.input_changed)
        layout.addWidget(self.locator)
        row = QHBoxLayout()
        self.file_label = QLabel("Nenhum arquivo selecionado")
        self.file_label.setWordWrap(True)
        row.addWidget(self.file_label, 1)
        choose = QPushButton("Selecionar arquivo…"); choose.clicked.connect(self.select_file_requested)
        row.addWidget(choose); layout.addLayout(row)
        row = QHBoxLayout()
        read = QPushButton("Ler QR de imagem…"); read.clicked.connect(self.read_qr_requested); row.addWidget(read)
        self.check = QPushButton("Verificar"); self.check.clicked.connect(self.check_requested); row.addWidget(self.check)
        config = QPushButton("Configuração de validação…"); config.clicked.connect(self.configure_requested)
        self.config = config; row.addWidget(config); layout.addLayout(row)
        self.matches = QComboBox()
        self.matches.setAccessibleName('Registros correspondentes ao hash')
        self.matches.currentIndexChanged.connect(self.matching_record_selected.emit)
        self.matches.hide()
        layout.addWidget(self.matches)
        self.result = QTextBrowser(); self.result.setOpenExternalLinks(False); layout.addWidget(self.result, 1)
        row = QHBoxLayout()
        self.open_original = QPushButton("Abrir original registrado")
        self.open_original.clicked.connect(self.open_original_requested)
        self.export = QPushButton("Baixar original registrado…"); self.export.clicked.connect(self.export_requested)
        self.revoke = QPushButton("Revogar registro…"); self.revoke.clicked.connect(self.revoke_requested)
        for widget in (self.open_original, self.export, self.revoke):
            widget.setEnabled(False); row.addWidget(widget)
        layout.addLayout(row)

    def clear_result(self):
        self.result.clear()
        self.matches.blockSignals(True); self.matches.clear(); self.matches.blockSignals(False); self.matches.hide()
        for button in (self.open_original, self.export, self.revoke):
            button.setEnabled(False)

    def display(self, result, *, can_export=True, can_revoke=False):
        import html
        record = result.record
        if result.matching_records:
            self.matches.blockSignals(True)
            self.matches.clear()
            for match in result.matching_records:
                self.matches.addItem(f'{match.human_code} — {match.status} — {match.logical_name_snapshot} — {match.created_at}')
            self.matches.setCurrentIndex(-1)
            self.matches.blockSignals(False)
            self.matches.show()
            self.result.setPlainText(result.message + '\n\n' + '\n'.join(
                f'{match.human_code}: {match.status}; {match.signature_type}; {match.created_at}; SHA-256 {match.final_sha256}' for match in result.matching_records))
            return
        if record is None:
            self.result.setPlainText(result.message or result.record_state)
            return
        lines = ["Original registrado associado a este QR",
                 f"Nome: {record.logical_name_snapshot}", f"Código: {record.human_code}",
                 f"Registro: {result.record_state}", f"Status administrativo: {record.status}",
                 f"Artefato: {result.artifact_state}", f"Arquivo fornecido: {result.file_integrity}",
                 f"Tipo: {record.artifact_type}", f"Assinatura: {record.signature_type}",
                 f"Validação criptográfica do original registrado: {result.signature_status}",
                 f"Confiança da cadeia: {result.trust_status}",
                 f"Criado em: {record.created_at}", f"SHA-256 registrado: {record.final_sha256 or '—'}"]
        if record.status == "REVOKED":
            lines += ["⚠ Registro revogado", f"Motivo: {record.revocation_reason}"]
        if result.file_integrity == "HASH_MISMATCH":
            lines += ["⚠ A cópia fornecida não é idêntica ao original registrado.",
                      "Alteração, reexportação, processamento por outro software ou corrupção podem mudar os bytes. A assinatura desta cópia não foi validada aqui."]
        elif result.file_integrity == "HASH_MATCH":
            lines += ["✓ Este arquivo é byte a byte idêntico ao original registrado."]
        elif result.file_integrity == "NOT_PROVIDED":
            lines += ["Apenas o registro foi localizado; forneça a cópia para comparar seus bytes."]
        if record.signature_type == "VISUAL_HANDWRITTEN":
            lines += ["Assinatura visual/manuscrita; identidade criptográfica não aplicável."]
        if result.artifact_state == "ARTIFACT_CORRUPTED":
            lines += ["O arquivo preservado pelo SmartFile não corresponde ao hash registrado."]
        if result.artifact_state == "ARTIFACT_MISSING":
            lines += ["O artefato canônico está ausente. Não é possível disponibilizar o original."]
        self.result.setHtml("<p>" + "<br>".join(html.escape(line) for line in lines) + "</p>")
        available = result.artifact_state == "AVAILABLE"
        self.open_original.setEnabled(available)
        self.export.setEnabled(available and can_export)
        self.revoke.setEnabled(record.status == "ACTIVE" and can_revoke)
