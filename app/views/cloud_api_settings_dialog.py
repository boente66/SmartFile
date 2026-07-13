from PyQt6.QtWidgets import QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QLabel,QLineEdit,QPushButton,QTabWidget,QVBoxLayout,QWidget


class CloudApiSettingsDialog(QDialog):
    def __init__(self,config_service,parent=None,initial_provider="ONEDRIVE"):
        super().__init__(parent); self.config=config_service; self.setWindowTitle("Configurar APIs da Nuvem"); self.resize(590,390); root=QVBoxLayout(self); self.tabs=QTabWidget(); root.addWidget(self.tabs)
        self.tabs.addTab(self._onedrive_page(),"Microsoft OneDrive"); self.tabs.addTab(self._google_page(),"Google Drive"); self.tabs.setCurrentIndex(1 if initial_provider=="GOOGLE_DRIVE" else 0)
        self.status=QLabel("As configurações são criptografadas no diretório de dados do SmartFile."); self.status.setWordWrap(True); root.addWidget(self.status); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Save); buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def _onedrive_page(self):
        page=QWidget(); form=QFormLayout(page); current=self.config.provider_config("ONEDRIVE"); self.ms_client_id=QLineEdit(current.get("client_id", "")); self.ms_tenant=QLineEdit(current.get("tenant","common")); form.addRow("Application (client) ID:",self.ms_client_id); form.addRow("Tenant:",self.ms_tenant); note=QLabel("Registre um aplicativo público Desktop/Mobile no Microsoft Entra e habilite http://localhost como redirect URI."); note.setWordWrap(True); form.addRow(note); return page
    def _google_page(self):
        page=QWidget(); form=QFormLayout(page); self.google_file=QLineEdit(); self.google_file.setReadOnly(True); choose=QPushButton("Selecionar JSON Desktop"); choose.clicked.connect(self._choose_google); form.addRow("Arquivo OAuth:",self.google_file); form.addRow("",choose); note=QLabel("No Google Cloud Console, habilite a Drive API e crie credenciais OAuth do tipo Aplicativo para computador."); note.setWordWrap(True); form.addRow(note); return page
    def _choose_google(self):
        path,_=QFileDialog.getOpenFileName(self,"Credenciais OAuth do Google","","JSON (*.json)")
        if path:self.google_file.setText(path)
    def _save(self):
        try:
            if self.ms_client_id.text().strip():self.config.save_onedrive(self.ms_client_id.text(),self.ms_tenant.text())
            if self.google_file.text():self.config.save_google_client_file(self.google_file.text())
            if not self.ms_client_id.text().strip() and not self.google_file.text():raise ValueError("Informe ao menos uma configuração OAuth.")
            self.accept()
        except Exception as exc:self.status.setText(str(exc))
