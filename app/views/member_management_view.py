from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog,QHBoxLayout,QHeaderView,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout


class MemberManagementView(QDialog):
    add_requested=pyqtSignal(); create_requested=pyqtSignal(); role_requested=pyqtSignal(int); deactivate_requested=pyqtSignal(int); remove_requested=pyqtSignal(int); transfer_requested=pyqtSignal(int)
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Usuários e Permissões"); self.resize(820,500); root=QVBoxLayout(self); self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(["Nome","Username","E-mail","Papel","Status","Último login","Entrada"]); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); root.addWidget(self.table); bar=QHBoxLayout()
        for text,slot in (("Adicionar existente",self.add_requested.emit),("Criar usuário",self.create_requested.emit),("Alterar papel",lambda:self._emit(self.role_requested)),("Desativar",lambda:self._emit(self.deactivate_requested)),("Remover",lambda:self._emit(self.remove_requested)),("Transferir propriedade",lambda:self._emit(self.transfer_requested))): button=QPushButton(text); button.clicked.connect(slot); bar.addWidget(button)
        root.addLayout(bar)
    def set_members(self,items):
        self.table.setRowCount(0)
        for membership,user in items:
            row=self.table.rowCount(); self.table.insertRow(row)
            for col,value in enumerate((user.display_name,user.username,user.email or "—",membership.role,membership.status,user.last_login_at or "—",membership.joined_at or membership.created_at)): self.table.setItem(row,col,QTableWidgetItem(str(value)))
            self.table.item(row,0).setData(256,user.id)
    def _emit(self,signal):
        row=self.table.currentRow()
        if row>=0: signal.emit(int(self.table.item(row,0).data(256)))
