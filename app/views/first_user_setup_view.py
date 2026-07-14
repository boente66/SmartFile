from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from app.models.registration_request import RegistrationRequest
from app.services.folder_template_service import FolderTemplateService
from app.ui.icon_provider import IconProvider


class RegistrationStepIndicator(QWidget):
    """Indicador leve e responsivo das quatro etapas do cadastro."""

    CAPTIONS = ("Dados pessoais", "Organização", "Template", "Resumo")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_step = 0
        self.completed = False
        self.setMinimumHeight(92)

    def set_step(self, step: int, completed: bool = False) -> None:
        self.current_step = max(0, min(3, int(step)))
        self.completed = completed
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = max(55, self.width() // 10)
        y = 31.0
        spacing = (self.width() - 2 * margin) / 3
        points = [QPointF(margin + index * spacing, y) for index in range(4)]
        for index in range(3):
            active = self.completed or index < self.current_step
            painter.setPen(QPen(QColor("#169b45" if active else "#d5dbe3"), 3 if active else 2))
            painter.drawLine(points[index] + QPointF(20, 0), points[index + 1] - QPointF(20, 0))
        for index, point in enumerate(points):
            active = self.completed or index <= self.current_step
            current = not self.completed and index == self.current_step
            painter.setPen(QPen(QColor("#169b45" if active else "#cbd3dd"), 2))
            painter.setBrush(QColor("#169b45") if current or self.completed else QColor("#ffffff"))
            painter.drawEllipse(point, 20, 20)
            painter.setPen(QColor("#ffffff" if current or self.completed else "#778397"))
            font = painter.font(); font.setBold(True); font.setPointSize(11); painter.setFont(font)
            painter.drawText(QRectF(point.x()-20, point.y()-20, 40, 40), Qt.AlignmentFlag.AlignCenter, "✓" if self.completed else str(index+1))
            painter.setPen(QColor("#169b45" if active else "#566174"))
            font.setPointSize(10); font.setBold(current or self.completed); painter.setFont(font)
            painter.drawText(QRectF(point.x()-75, 57, 150, 28), Qt.AlignmentFlag.AlignCenter, self.CAPTIONS[index])


class FirstUserSetupView(QWidget):
    registration_requested = pyqtSignal(object)
    back_requested = pyqtSignal()
    enter_requested = pyqtSignal()

    def __init__(self, first_user: bool = True):
        super().__init__()
        self.first_user = first_user
        self.avatar_path: str | None = None
        self._registration_complete = False
        self.setObjectName("authWindow")
        self.setWindowTitle("SmartFile — Criar conta e organização")
        self.resize(1360, 820)
        self.setMinimumSize(940, 650)
        self.setWindowIcon(IconProvider.icon("app"))
        self._setup_ui()
        self._connect_validation()
        self._update_navigation()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content.setObjectName("registrationContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 18, 28, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.top_back_button = QPushButton("←  Voltar ao login")
        self.top_back_button.setObjectName("registrationBackLink")
        self.top_back_button.clicked.connect(self.back_requested.emit)
        top.addWidget(self.top_back_button)
        top.addStretch()
        layout.addLayout(top)

        title = QLabel("Criar conta e organização")
        title.setObjectName("registrationTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.steps_label = QLabel()
        self.steps_label.setObjectName("registrationStepCaption")
        self.steps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.steps_label)
        self.step_indicator = RegistrationStepIndicator()
        layout.addWidget(self.step_indicator)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("registrationScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        self.stack.setObjectName("registrationStack")
        self.stack.addWidget(self._personal_page())
        self.stack.addWidget(self._organization_page())
        self.stack.addWidget(self._template_page())
        self.stack.addWidget(self._summary_page())
        self.scroll.setWidget(self.stack)
        layout.addWidget(self.scroll, 1)

        self.error_label = QLabel()
        self.error_label.setObjectName("authError")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_label)
        root.addWidget(content, 1)

        actions_frame = QFrame()
        actions_frame.setObjectName("registrationActions")
        actions = QHBoxLayout(actions_frame)
        actions.setContentsMargins(28, 14, 28, 14)
        self.cancel_button = QPushButton("Voltar ao login")
        self.cancel_button.setObjectName("registrationSecondary")
        self.cancel_button.clicked.connect(self.back_requested.emit)
        self.back_button = QPushButton("←  Voltar")
        self.back_button.setObjectName("registrationSecondary")
        self.back_button.clicked.connect(self.previous_step)
        self.next_button = QPushButton("Continuar  →")
        self.next_button.setObjectName("authPrimary")
        self.next_button.clicked.connect(self.next_step)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.back_button)
        actions.addWidget(self.next_button)
        root.addWidget(actions_frame)

        footer = QFrame()
        footer.setObjectName("registrationFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(32, 10, 32, 10)
        secure = QLabel("✓  Seus dados são protegidos e armazenados localmente com segurança.")
        secure.setObjectName("registrationSecureText")
        footer_layout.addWidget(secure)
        footer_layout.addStretch()
        footer_layout.addWidget(QLabel("SmartFile Desktop  •  Seguro"))
        root.addWidget(footer)

    def _personal_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("registrationPage")
        root = QHBoxLayout(page)
        root.setContentsMargins(18, 6, 18, 12)
        root.setSpacing(42)

        fields = QWidget()
        grid = QGridLayout(fields)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)
        self.display_name = self._field(grid, 0, 0, "Nome completo", "Digite seu nome completo", "user")
        self.username = self._field(grid, 0, 1, "Nome de usuário", "Escolha um nome de usuário", "user")
        self.username_status = QLabel("Use letras, números, ponto, hífen ou sublinhado")
        self.username_status.setObjectName("registrationValidation")
        grid.addWidget(self.username_status, 2, 1)
        self.email = self._field(grid, 3, 0, "E-mail (opcional)", "seu@email.com", "mail")
        self.phone = self._field(grid, 3, 1, "Telefone (opcional)", "(11) 99999-9999", "phone")
        self.password = self._field(grid, 6, 0, "Senha", "Mínimo de 8 caracteres", "lock", True)
        self.confirmation = self._field(grid, 6, 1, "Confirmar senha", "Repita a senha", "lock", True)

        strength_row = QHBoxLayout()
        self.strength_bars = []
        for _ in range(4):
            bar = QFrame(); bar.setObjectName("passwordStrengthBar"); bar.setFixedHeight(5)
            strength_row.addWidget(bar); self.strength_bars.append(bar)
        self.strength_label = QLabel("Informe uma senha")
        self.strength_label.setObjectName("passwordStrengthLabel")
        strength_row.addWidget(self.strength_label)
        grid.addWidget(QLabel("Força da senha"), 9, 0)
        grid.addLayout(strength_row, 10, 0)
        self.password_match = QLabel("As senhas devem coincidir")
        self.password_match.setObjectName("registrationValidation")
        grid.addWidget(self.password_match, 10, 1)
        self.password_requirements = QLabel()
        self.password_requirements.setObjectName("passwordRequirements")
        self.password_requirements.setWordWrap(True)
        grid.addWidget(self.password_requirements, 11, 0, 1, 2)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        root.addWidget(fields, 4)

        avatar = QFrame()
        avatar.setObjectName("avatarPanel")
        avatar_layout = QVBoxLayout(avatar)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        caption = QLabel("Avatar (opcional)"); caption.setObjectName("registrationFieldLabel")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_layout.addWidget(caption)
        self.avatar_preview = QLabel("AL")
        self.avatar_preview.setObjectName("avatarPreview")
        self.avatar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_preview.setFixedSize(170, 170)
        avatar_layout.addWidget(self.avatar_preview, 0, Qt.AlignmentFlag.AlignHCenter)
        self.avatar_label = QLabel("Nenhum avatar selecionado")
        self.avatar_label.setObjectName("registrationHint")
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_layout.addWidget(self.avatar_label)
        choose = QPushButton("Selecionar avatar")
        choose.setObjectName("avatarChooseButton")
        IconProvider.apply(choose, "image")
        choose.clicked.connect(self._select_avatar)
        remove = QPushButton("Remover avatar")
        remove.setObjectName("avatarRemoveButton")
        IconProvider.apply(remove, "action_trash")
        remove.clicked.connect(self._remove_avatar)
        avatar_layout.addWidget(choose)
        avatar_layout.addWidget(remove)
        root.addWidget(avatar, 1)
        return page

    def _organization_page(self) -> QWidget:
        page = QWidget(); page.setObjectName("registrationPage")
        root = QVBoxLayout(page); root.setContentsMargins(80, 12, 80, 20); root.setSpacing(16)
        heading = QLabel("Configure sua organização")
        heading.setObjectName("registrationSectionTitle")
        root.addWidget(heading)
        hint = QLabel("A organização separa documentos, pastas, histórico e sincronização.")
        hint.setObjectName("registrationHint"); root.addWidget(hint)
        form = QFormLayout(); form.setSpacing(14)
        self.organization_name = QLineEdit("Minha Organização")
        self.organization_description = QTextEdit(); self.organization_description.setMaximumHeight(110)
        self.organization_description.setPlaceholderText("Descreva brevemente esta organização")
        self.organization_icon = QComboBox(); self.organization_icon.addItems(["organization", "business", "school", "folder", "home"])
        self.organization_color = QComboBox(); self.organization_color.addItems(["#2563eb", "#16a34a", "#7c3aed", "#ea580c", "#dc2626"])
        form.addRow("Nome da organização:", self.organization_name)
        form.addRow("Descrição (opcional):", self.organization_description)
        form.addRow("Ícone:", self.organization_icon)
        form.addRow("Cor:", self.organization_color)
        root.addLayout(form); root.addStretch()
        return page

    def _template_page(self) -> QWidget:
        page = QWidget(); page.setObjectName("registrationPage")
        root = QVBoxLayout(page); root.setContentsMargins(38, 6, 38, 18); root.setSpacing(14)
        heading = QLabel("Escolha uma estrutura inicial")
        heading.setObjectName("registrationSectionTitle"); root.addWidget(heading)
        hint = QLabel("O template cria pastas iniciais. O plano de armazenamento é independente.")
        hint.setObjectName("registrationHint"); root.addWidget(hint)
        self.storage_plan = QComboBox()
        self.storage_plan.addItem("Pessoal — 10 GB", "PERSONAL_10GB")
        self.storage_plan.addItem("Estudante — 20 GB", "STUDENT_20GB")
        self.storage_plan.addItem("Empresarial — 60 GB", "BUSINESS_60GB")
        cards = QGridLayout(); cards.setSpacing(14)
        self.templates = QButtonGroup(self); self.templates.setExclusive(True)
        descriptions = {
            "PERSONAL": "Documentos pessoais, contas, garantias, saúde e comprovantes.",
            "STUDENT": "Disciplinas, trabalhos, projetos, certificados e materiais.",
            "BUSINESS": "Financeiro, fiscal, RH, contratos, clientes e projetos.",
            "EMPTY": "Não cria pastas iniciais. Comece sua estrutura do zero.",
        }
        for index, (code, name) in enumerate((("PERSONAL", "Pessoal"), ("STUDENT", "Estudante"), ("BUSINESS", "Empresarial"), ("EMPTY", "Começar vazio"))):
            radio = QRadioButton(f"{name}\n{descriptions[code]}")
            radio.setObjectName("templateCard"); radio.setProperty("templateCode", code)
            radio.setMinimumHeight(105); radio.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.templates.addButton(radio); cards.addWidget(radio, index // 2, index % 2)
            radio.toggled.connect(lambda checked, value=code: checked and self._suggest_plan(value))
            if index == 0: radio.setChecked(True)
        root.addLayout(cards)
        plan_row = QFormLayout(); plan_row.addRow("Plano de armazenamento lógico:", self.storage_plan)
        root.addLayout(plan_row); root.addStretch()
        return page

    def _summary_page(self) -> QWidget:
        page = QWidget(); page.setObjectName("registrationPage")
        root = QVBoxLayout(page); root.setContentsMargins(80, 12, 80, 24); root.setSpacing(16)
        self.summary_title = QLabel("Revise antes de finalizar")
        self.summary_title.setObjectName("registrationSectionTitle"); self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary = QLabel(); self.summary.setObjectName("registrationSummary"); self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.completion = QLabel(); self.completion.setObjectName("registrationCompletion")
        self.completion.setAlignment(Qt.AlignmentFlag.AlignCenter); self.completion.setWordWrap(True); self.completion.hide()
        root.addWidget(self.summary_title); root.addWidget(self.summary); root.addWidget(self.completion); root.addStretch()
        return page

    def _field(self, layout, row, column, label, placeholder, icon, password=False):
        caption = QLabel(label); caption.setObjectName("registrationFieldLabel")
        layout.addWidget(caption, row, column)
        field = QLineEdit(); field.setPlaceholderText(placeholder); field.setMinimumHeight(48)
        field.setEchoMode(QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal)
        field.addAction(IconProvider.icon(icon), QLineEdit.ActionPosition.LeadingPosition)
        if password:
            visibility = field.addAction(
                IconProvider.icon("visualize"), QLineEdit.ActionPosition.TrailingPosition
            )
            visibility.setToolTip("Mostrar ou ocultar senha")
            visibility.triggered.connect(
                lambda _checked=False, target=field: target.setEchoMode(
                    QLineEdit.EchoMode.Normal
                    if target.echoMode() == QLineEdit.EchoMode.Password
                    else QLineEdit.EchoMode.Password
                )
            )
        layout.addWidget(field, row + 1, column)
        return field

    def _connect_validation(self) -> None:
        self.display_name.textChanged.connect(self._update_avatar_initials)
        self.username.textChanged.connect(self._update_username_status)
        self.password.textChanged.connect(self._update_password_strength)
        self.confirmation.textChanged.connect(self._update_password_strength)
        self._update_password_strength()
        self._update_avatar_initials()

    def next_step(self) -> None:
        index = self.stack.currentIndex(); self.error_label.clear()
        if self._registration_complete:
            self.enter_requested.emit(); return
        if index == 0 and not self._validate_personal(): return
        if index == 1 and not self.organization_name.text().strip():
            self.show_error("Informe o nome da organização."); self.organization_name.setFocus(); return
        if index == 2:
            self._refresh_summary()
        if index == 3:
            self.registration_requested.emit(self.request()); return
        self.stack.setCurrentIndex(index + 1)
        self.scroll.verticalScrollBar().setValue(0)
        self._update_navigation()

    def previous_step(self) -> None:
        if self._registration_complete: return
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
            self._update_navigation()

    def request(self) -> RegistrationRequest:
        selected = self.templates.checkedButton()
        code = str(selected.property("templateCode")) if selected else ""
        return RegistrationRequest(
            display_name=self.display_name.text(), username=self.username.text(),
            email=self.email.text() or None, phone=self.phone.text() or None,
            password=self.password.text(), password_confirmation=self.confirmation.text(),
            template_code=code, storage_plan_code=str(self.storage_plan.currentData()),
            organization_name=self.organization_name.text(),
            organization_description=self.organization_description.toPlainText() or None,
            organization_icon=self.organization_icon.currentText(),
            organization_color=self.organization_color.currentText(), avatar_path=self.avatar_path,
        )

    def show_completion(self) -> None:
        count = len(FolderTemplateService.TEMPLATES[self.request().template_code])
        self._registration_complete = True
        self.stack.setCurrentIndex(3)
        self.summary.hide()
        self.summary_title.setText("✓ Cadastro concluído")
        self.completion.setText(
            f"Sua conta e a organização <b>{self.organization_name.text().strip()}</b> foram criadas.<br>"
            f"{count} pasta(s) inicial(is) configurada(s) · Papel inicial: OWNER"
        )
        self.completion.show()
        self._update_navigation()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)

    def _validate_personal(self) -> bool:
        if not self.display_name.text().strip() or not self.username.text().strip():
            self.show_error("Informe nome completo e nome de usuário."); return False
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.username.text().strip()):
            self.show_error("O nome de usuário contém caracteres inválidos."); return False
        if len(self.password.text()) < 8:
            self.show_error("A senha deve possuir pelo menos 8 caracteres."); return False
        if self.password.text() != self.confirmation.text():
            self.show_error("As senhas não coincidem."); return False
        return True

    def _refresh_summary(self) -> None:
        request = self.request(); folders = FolderTemplateService.TEMPLATES.get(request.template_code, ())
        self.summary.setText(
            f"<div style='line-height:150%'><b>Usuário:</b> {request.display_name}<br>"
            f"<b>Nome de usuário:</b> {request.username}<br><b>Organização:</b> {request.organization_name}<br>"
            f"<b>Template:</b> {request.template_code}<br><b>Plano:</b> {self.storage_plan.currentText()}<br>"
            f"<b>Papel:</b> OWNER<br><b>Pastas:</b> {', '.join(folders) if folders else 'Nenhuma pasta automática'}</div>"
        )

    def _suggest_plan(self, template_code: str) -> None:
        plan = {"PERSONAL": "PERSONAL_10GB", "STUDENT": "STUDENT_20GB", "BUSINESS": "BUSINESS_60GB", "EMPTY": "PERSONAL_10GB"}.get(template_code, "PERSONAL_10GB")
        index = self.storage_plan.findData(plan)
        if index >= 0: self.storage_plan.setCurrentIndex(index)

    def _update_navigation(self) -> None:
        index = self.stack.currentIndex()
        names = ("Dados pessoais", "Organização", "Template e armazenamento", "Resumo")
        self.steps_label.setText(f"Etapa {index + 1} de 4 — {names[index]}")
        self.step_indicator.set_step(index, self._registration_complete)
        self.back_button.setVisible(index > 0 and not self._registration_complete)
        self.cancel_button.setVisible(not self._registration_complete)
        self.top_back_button.setVisible(not self._registration_complete)
        if self._registration_complete:
            self.next_button.setText("Entrar no SmartFile  →")
        elif index == 3:
            self.next_button.setText("Criar conta  →")
        else:
            self.next_button.setText("Continuar  →")

    def _update_username_status(self, value: str) -> None:
        valid = bool(value and re.fullmatch(r"[A-Za-z0-9._-]+", value))
        self.username_status.setText("✓ Nome de usuário válido" if valid else "Use letras, números, ponto, hífen ou sublinhado")
        self.username_status.setProperty("valid", valid)
        self.username_status.style().unpolish(self.username_status); self.username_status.style().polish(self.username_status)

    def _update_password_strength(self) -> None:
        value = self.password.text()
        checks = [len(value) >= 8, bool(re.search(r"[A-Z]", value) and re.search(r"[a-z]", value)), bool(re.search(r"\d", value)), bool(re.search(r"[^A-Za-z0-9]", value))]
        score = sum(checks)
        colors = ("#d7dde5", "#ef4444", "#f59e0b", "#84cc16", "#169b45")
        for index, bar in enumerate(self.strength_bars):
            bar.setStyleSheet(f"background:{colors[score] if index < score else '#d7dde5'}; border-radius:2px;")
        self.strength_label.setText(("Informe uma senha", "Fraca", "Regular", "Boa", "Forte")[score])
        requirements = (("Mínimo de 8 caracteres", checks[0]), ("Letras maiúsculas e minúsculas", checks[1]), ("Números", checks[2]), ("Caractere especial", checks[3]))
        self.password_requirements.setText("   ".join(("✓" if ok else "○") + " " + text for text, ok in requirements))
        matches = bool(self.confirmation.text()) and value == self.confirmation.text()
        self.password_match.setText("✓ As senhas coincidem" if matches else "As senhas devem coincidir")
        self.password_match.setProperty("valid", matches)
        self.password_match.style().unpolish(self.password_match); self.password_match.style().polish(self.password_match)

    def _update_avatar_initials(self) -> None:
        if self.avatar_path: return
        parts = self.display_name.text().split()
        initials = "".join(part[0].upper() for part in parts[:2]) or "SF"
        self.avatar_preview.setPixmap(QPixmap())
        self.avatar_preview.setText(initials)

    def _select_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar avatar", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
        if not path: return
        source = QPixmap(path)
        if source.isNull(): self.show_error("A imagem selecionada não pôde ser carregada."); return
        self.avatar_path = path; self.avatar_label.setText(Path(path).name)
        size = 160
        target = QPixmap(size, size); target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath(); clip.addEllipse(0, 0, size, size); painter.setClipPath(clip)
        scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap((size-scaled.width())//2, (size-scaled.height())//2, scaled); painter.end()
        self.avatar_preview.setText(""); self.avatar_preview.setPixmap(target)

    def _remove_avatar(self) -> None:
        self.avatar_path = None; self.avatar_label.setText("Nenhum avatar selecionado")
        self._update_avatar_initials()
