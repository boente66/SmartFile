from PyQt6.QtWidgets import QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QVBoxLayout


class ProfileDialog(QDialog):
    def __init__(self,user,parent=None):
        super().__init__(parent); self.setWindowTitle("Meu Perfil"); root=QVBoxLayout(self); form=QFormLayout(); self.name=QLineEdit(user.display_name); self.email=QLineEdit(user.email or ""); self.phone=QLineEdit(user.phone or ""); self.avatar_path=None; self.remove_avatar=False; self.avatar=QLabel(user.avatar_path or user.avatar_initials or "Sem avatar"); row=QHBoxLayout(); choose=QPushButton("Selecionar"); choose.clicked.connect(self._choose); remove=QPushButton("Remover"); remove.clicked.connect(self._remove); row.addWidget(self.avatar); row.addWidget(choose); row.addWidget(remove); form.addRow("Nome completo:",self.name); form.addRow("E-mail:",self.email); form.addRow("Telefone:",self.phone); form.addRow("Avatar:",row); root.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Save); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def _choose(self):
        path,_=QFileDialog.getOpenFileName(self,"Avatar","","Imagens (*.png *.jpg *.jpeg *.webp)")
        if path: self.avatar_path=path; self.remove_avatar=False; self.avatar.setText(path)
    def _remove(self): self.avatar_path=None; self.remove_avatar=True; self.avatar.setText("Sem avatar")
