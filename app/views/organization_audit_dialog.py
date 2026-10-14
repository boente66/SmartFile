from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (QDialog,QDialogButtonBox,QHeaderView,QTableWidget,
    QTableWidgetItem,QVBoxLayout,QHBoxLayout,QLineEdit,QPushButton,QLabel)
from app.views.widgets.corporate_header import CorporateHeader
from app.views.widgets.dialog_theme import apply_import_theme


class OrganizationAuditDialog(QDialog):
    query_requested=pyqtSignal(dict)
    export_requested=pyqtSignal(str)

    def __init__(self,rows=(),parent=None,*,identity=None,administrative=True):
        super().__init__(parent)
        apply_import_theme(self)
        self.setWindowTitle('SmartFile — Histórico/Auditoria')
        self.resize(1150,620)
        root=QVBoxLayout(self)
        if identity:
            header=CorporateHeader();header.apply_identity(identity);root.addWidget(header)
        self.filters={}
        if administrative:
            row=QHBoxLayout()
            for key,label in (('actor_username','Usuário'),('document_name','Documento'),('action','Ação'),('instance_id','Instalação'),('from_date','Início AAAA-MM-DD'),('to_date','Fim AAAA-MM-DD')):
                edit=QLineEdit();edit.setPlaceholderText(label);edit.setAccessibleName(label)
                self.filters[key]=edit;row.addWidget(edit)
            query=QPushButton('Consultar');query.clicked.connect(lambda:self.query_requested.emit(self.values()));row.addWidget(query);root.addLayout(row)
        self.table=QTableWidget(0,11)
        self.table.setHorizontalHeaderLabels(['Data UTC','Usuário SmartFile','Ação','Organização','Instalação','Documento','Origem','SHA-256 anterior','SHA-256 novo','Descrição','Evidências'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table,1)
        self.info=QLabel();self.info.setWordWrap(True);root.addWidget(self.info)
        if administrative:
            row=QHBoxLayout()
            for kind,label in (('CSV','Exportar CSV'),('PDF','Relatório PDF')):
                button=QPushButton(label);button.clicked.connect(lambda _,k=kind:self.export_requested.emit(k));row.addWidget(button)
            root.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject);root.addWidget(buttons)
        self.set_rows(rows)

    def values(self):
        values={key:edit.text().strip() for key,edit in self.filters.items() if edit.text().strip()}
        if len(values.get('to_date',''))==10:values['to_date']+='T23:59:59.999999+00:00'
        if len(values.get('from_date',''))==10:values['from_date']+='T00:00:00+00:00'
        return values

    def set_rows(self,rows):
        self.table.setRowCount(len(rows))
        for index,row in enumerate(rows):
            values=(row.created_at,row.actor_username or 'LEGACY_UNKNOWN',row.action,row.organization_name or '—',row.instance_id or 'Desconhecida (legado)',row.document_name or row.document_uuid or '—',row.source_type or '—',row.sha256_before or '—',row.sha256_after or '—',row.description or '',row.details_json or '')
            for column,value in enumerate(values):self.table.setItem(index,column,QTableWidgetItem(str(value)))
        self.info.setText(f'{len(rows)} evento(s). Limite de consulta: 5.000. Histórico consolidado somente para leitura; atores legados não são inferidos.')
