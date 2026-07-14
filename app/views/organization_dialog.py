from PyQt6.QtWidgets import QComboBox,QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QTextEdit,QVBoxLayout


class OrganizationDialog(QDialog):
    def __init__(self,parent=None,organization=None,show_template=True):
        super().__init__(parent); self.setWindowTitle("Organização"); self.resize(440,330); root=QVBoxLayout(self); form=QFormLayout()
        self.name=QLineEdit(getattr(organization,"name","") or ""); self.description=QTextEdit(getattr(organization,"description","") or ""); self.description.setMaximumHeight(80); self.icon=QComboBox(); self.icon.addItems(["organization","business","school","folder","home"]); self.color=QComboBox(); self.color.addItems(["#2563eb","#16a34a","#7c3aed","#ea580c","#dc2626"]); self.template=QComboBox(); self.template.addItems(["EMPTY","PERSONAL","STUDENT","BUSINESS"]); self.storage_plan=QComboBox(); self.storage_plan.addItem("Pessoal — 10 GB","PERSONAL_10GB"); self.storage_plan.addItem("Estudante — 20 GB","STUDENT_20GB"); self.storage_plan.addItem("Empresarial — 60 GB","BUSINESS_60GB"); self.activate=QComboBox(); self.activate.addItems(["Não ativar agora","Ativar após criar"])
        if organization:
            self.icon.setCurrentText(organization.icon or "organization"); self.color.setCurrentText(organization.color or "#2563eb")
        form.addRow("Nome:",self.name); form.addRow("Descrição:",self.description); form.addRow("Ícone:",self.icon); form.addRow("Cor:",self.color)
        if show_template: form.addRow("Template:",self.template); form.addRow("Plano:",self.storage_plan); form.addRow("Após criar:",self.activate)
        root.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def values(self): return {"name":self.name.text(),"description":self.description.toPlainText() or None,"icon":self.icon.currentText(),"color":self.color.currentText(),"template":self.template.currentText(),"storage_plan_code":str(self.storage_plan.currentData()),"activate":self.activate.currentIndex()==1}
