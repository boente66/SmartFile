from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup,QComboBox,QFileDialog,QFormLayout,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QRadioButton,QScrollArea,QStackedWidget,QTextEdit,QVBoxLayout,QWidget)

from app.models.registration_request import RegistrationRequest
from app.services.folder_template_service import FolderTemplateService
from app.ui.icon_provider import IconProvider


class FirstUserSetupView(QWidget):
    registration_requested=pyqtSignal(object); back_requested=pyqtSignal(); enter_requested=pyqtSignal()
    def __init__(self,first_user=True):
        super().__init__(); self.first_user=first_user; self.avatar_path=None; self.setObjectName("authWindow"); self.setWindowTitle("SmartFile — Criar conta"); self.resize(1100,720); self.setMinimumSize(820,580); self.setWindowIcon(IconProvider.icon("app"))
        outer=QVBoxLayout(self); outer.setContentsMargins(24,18,24,18)
        title=QLabel("Criar conta e organização"); title.setObjectName("authTitle"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); outer.addWidget(title)
        self.steps_label=QLabel(); self.steps_label.setAlignment(Qt.AlignmentFlag.AlignCenter); outer.addWidget(self.steps_label)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame); container=QWidget(); layout=QVBoxLayout(container)
        self.stack=QStackedWidget(); self.stack.addWidget(self._personal_page()); self.stack.addWidget(self._organization_page()); self.stack.addWidget(self._summary_page()); self.stack.addWidget(self._completion_page()); layout.addWidget(self.stack); scroll.setWidget(container); outer.addWidget(scroll,1)
        self.error_label=QLabel(); self.error_label.setObjectName("authError"); self.error_label.setWordWrap(True); outer.addWidget(self.error_label)
        actions=QHBoxLayout(); self.cancel_button=QPushButton("Cancelar" if first_user else "Voltar ao login"); self.cancel_button.clicked.connect(self.back_requested); self.back_button=QPushButton("Voltar"); self.back_button.clicked.connect(self.previous_step); self.next_button=QPushButton("Continuar"); self.next_button.setObjectName("authPrimary"); self.next_button.clicked.connect(self.next_step); actions.addWidget(self.cancel_button); actions.addStretch(); actions.addWidget(self.back_button); actions.addWidget(self.next_button); outer.addLayout(actions); self._update_navigation()

    def _personal_page(self):
        page=QWidget(); form=QGridLayout(page); form.setSpacing(12)
        self.display_name=self._field(form,0,0,"Nome completo","Digite seu nome completo"); self.username=self._field(form,0,1,"Nome de usuário","Escolha um nome de usuário")
        self.email=self._field(form,2,0,"E-mail (opcional)","seu@email.com"); self.phone=self._field(form,2,1,"Telefone (opcional)","(11) 99999-9999")
        self.password=self._field(form,4,0,"Senha","Mínimo de 8 caracteres",True); self.confirmation=self._field(form,4,1,"Confirmar senha","Repita a senha",True)
        self.avatar_label=QLabel("Nenhum avatar selecionado"); choose=QPushButton("Selecionar avatar"); choose.clicked.connect(self._select_avatar); remove=QPushButton("Remover"); remove.clicked.connect(self._remove_avatar); row=QHBoxLayout(); row.addWidget(self.avatar_label,1); row.addWidget(choose); row.addWidget(remove); form.addWidget(QLabel("Avatar (opcional)"),6,0); form.addLayout(row,7,0,1,2)
        return page

    def _organization_page(self):
        page=QWidget(); root=QVBoxLayout(page); form=QFormLayout(); self.organization_name=QLineEdit("Minha Organização"); self.organization_description=QTextEdit(); self.organization_description.setMaximumHeight(80); self.organization_icon=QComboBox(); self.organization_icon.addItems(["organization","business","school","folder","home"]); self.organization_color=QComboBox(); self.organization_color.addItems(["#2563eb","#16a34a","#7c3aed","#ea580c","#dc2626"]); form.addRow("Nome da organização:",self.organization_name); form.addRow("Descrição:",self.organization_description); form.addRow("Ícone:",self.organization_icon); form.addRow("Cor:",self.organization_color); root.addLayout(form); root.addWidget(QLabel("Modelo inicial de pastas"))
        cards=QHBoxLayout(); self.templates=QButtonGroup(self); self.templates.setExclusive(True)
        for index,(code,name) in enumerate((("PERSONAL","Pessoal"),("STUDENT","Estudante"),("BUSINESS","Empresarial"),("EMPTY","Começar vazio"))):
            radio=QRadioButton(name); radio.setObjectName("templateCard"); radio.setProperty("templateCode",code); radio.setMinimumHeight(70); self.templates.addButton(radio); cards.addWidget(radio)
            if index==0: radio.setChecked(True)
        root.addLayout(cards); return page

    def _summary_page(self):
        page=QWidget(); root=QVBoxLayout(page); self.summary=QLabel(); self.summary.setWordWrap(True); self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); root.addWidget(self.summary); root.addStretch(); return page

    def _completion_page(self):
        page=QWidget(); root=QVBoxLayout(page); label=QLabel("✓ Cadastro concluído"); label.setObjectName("authTitle"); label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.completion=QLabel(); self.completion.setAlignment(Qt.AlignmentFlag.AlignCenter); self.completion.setWordWrap(True); root.addStretch(); root.addWidget(label); root.addWidget(self.completion); root.addStretch(); return page

    @staticmethod
    def _field(layout,row,column,label,placeholder,password=False):
        layout.addWidget(QLabel(label),row,column); field=QLineEdit(); field.setPlaceholderText(placeholder); field.setEchoMode(QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal); layout.addWidget(field,row+1,column); return field

    def next_step(self):
        index=self.stack.currentIndex(); self.error_label.clear()
        if index==0 and not self._validate_personal(): return
        if index==1:
            if not self.organization_name.text().strip(): self.show_error("Informe o nome da organização."); return
            self._refresh_summary()
        if index==2: self.registration_requested.emit(self.request()); return
        if index==3: self.enter_requested.emit(); return
        self.stack.setCurrentIndex(index+1); self._update_navigation()

    def previous_step(self):
        if self.stack.currentIndex()>0: self.stack.setCurrentIndex(self.stack.currentIndex()-1); self._update_navigation()

    def request(self):
        selected=self.templates.checkedButton(); code=str(selected.property("templateCode")) if selected else ""
        return RegistrationRequest(display_name=self.display_name.text(),username=self.username.text(),email=self.email.text() or None,phone=self.phone.text() or None,password=self.password.text(),password_confirmation=self.confirmation.text(),template_code=code,organization_name=self.organization_name.text(),organization_description=self.organization_description.toPlainText() or None,organization_icon=self.organization_icon.currentText(),organization_color=self.organization_color.currentText(),avatar_path=self.avatar_path)

    def _submit(self): self.registration_requested.emit(self.request())
    def show_completion(self):
        count=len(FolderTemplateService.TEMPLATES[self.request().template_code]); self.completion.setText(f"Organização {self.organization_name.text().strip()} criada com {count} pasta(s).\nPapel inicial: OWNER"); self.stack.setCurrentIndex(3); self._update_navigation()
    def show_error(self,message): self.error_label.setText(message)
    def _validate_personal(self):
        if not self.display_name.text().strip() or not self.username.text().strip(): self.show_error("Informe nome completo e username."); return False
        if len(self.password.text())<8: self.show_error("A senha deve possuir pelo menos 8 caracteres."); return False
        if self.password.text()!=self.confirmation.text(): self.show_error("As senhas não coincidem."); return False
        return True
    def _refresh_summary(self):
        request=self.request(); folders=FolderTemplateService.TEMPLATES.get(request.template_code,()); self.summary.setText(f"<h2>Revise antes de finalizar</h2><b>Usuário:</b> {request.display_name}<br><b>Username:</b> {request.username}<br><b>Organização:</b> {request.organization_name}<br><b>Template:</b> {request.template_code}<br><b>Papel:</b> OWNER<br><b>Pastas:</b> {', '.join(folders) if folders else 'Nenhuma pasta automática'}")
    def _update_navigation(self):
        index=self.stack.currentIndex(); self.steps_label.setText(f"Etapa {index+1} de 4 — "+("Dados pessoais","Organização","Resumo","Conclusão")[index]); self.back_button.setVisible(index in (1,2)); self.cancel_button.setVisible(index<3); self.next_button.setText(("Continuar","Continuar","Finalizar","Entrar no SmartFile")[index])
    def _select_avatar(self):
        path,_=QFileDialog.getOpenFileName(self,"Selecionar avatar","","Imagens (*.png *.jpg *.jpeg *.webp)")
        if path: self.avatar_path=path; self.avatar_label.setText(Path(path).name)
    def _remove_avatar(self): self.avatar_path=None; self.avatar_label.setText("Nenhum avatar selecionado")
