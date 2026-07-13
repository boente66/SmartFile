from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout


class ChangePasswordDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Alterar senha")
        root=QVBoxLayout(self); form=QFormLayout()
        self.current=QLineEdit(); self.new=QLineEdit(); self.confirmation=QLineEdit()
        for field in (self.current,self.new,self.confirmation): field.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Senha atual:",self.current); form.addRow("Nova senha:",self.new); form.addRow("Confirmar:",self.confirmation); root.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
