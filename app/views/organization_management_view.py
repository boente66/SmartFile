from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog,QHBoxLayout,QHeaderView,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout


class OrganizationManagementView(QDialog):
    create_requested=pyqtSignal(); open_requested=pyqtSignal(int); edit_requested=pyqtSignal(int); duplicate_requested=pyqtSignal(int); archive_requested=pyqtSignal(int); members_requested=pyqtSignal(int)
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Gerenciar Organizações"); self.resize(920,560); root=QVBoxLayout(self); self.search=QLineEdit(); self.search.setPlaceholderText("Buscar organização..."); self.search.textChanged.connect(self._filter); root.addWidget(self.search); self.table=QTableWidget(0,10); self.table.setHorizontalHeaderLabels(["Nome","Papel","Documentos","Pastas","Membros","Nuvem","Status","Criada em","Última atividade","Descrição"]); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setStretchLastSection(True); root.addWidget(self.table)
        bar=QHBoxLayout(); specs=(("Nova",self.create_requested.emit),("Abrir",lambda:self._emit(self.open_requested)),("Editar",lambda:self._emit(self.edit_requested)),("Duplicar estrutura",lambda:self._emit(self.duplicate_requested)),("Arquivar",lambda:self._emit(self.archive_requested)),("Usuários e permissões",lambda:self._emit(self.members_requested)))
        for text,slot in specs: button=QPushButton(text); button.clicked.connect(slot); bar.addWidget(button)
        bar.addStretch(); close=QPushButton("Fechar"); close.clicked.connect(self.accept); bar.addWidget(close); root.addLayout(bar)
    def set_items(self,items):
        self.table.setRowCount(0)
        for organization,membership,stats in items:
            row=self.table.rowCount(); self.table.insertRow(row); values=(organization.name,membership.role,stats["documents"],stats["folders"],stats["members"],stats["cloud"],"ARQUIVADA" if organization.archived_at else organization.status,organization.created_at,stats["last_activity"] or "—",organization.description or "")
            for column,value in enumerate(values): self.table.setItem(row,column,QTableWidgetItem(str(value)))
            self.table.item(row,0).setData(256,organization.id)
    def selected_id(self):
        row=self.table.currentRow(); return int(self.table.item(row,0).data(256)) if row>=0 else None
    def _emit(self,signal):
        value=self.selected_id()
        if value is not None: signal.emit(value)
    def _filter(self,text):
        value=text.casefold()
        for row in range(self.table.rowCount()): self.table.setRowHidden(row,value not in self.table.item(row,0).text().casefold())
