from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from app.services.organization_feature_service import OrganizationFeatureService


class OrganizationDialog(QDialog):
    def __init__(
        self, parent=None, organization=None, show_template=True,
        enabled_features: set[str] | frozenset[str] | None = None,
    ):
        super().__init__(parent)
        self.feature_policy = OrganizationFeatureService()
        self.setWindowTitle("Configurações da organização")
        self.resize(680, 680)
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit(getattr(organization, "name", "") or "")
        self.description = QTextEdit(getattr(organization, "description", "") or "")
        self.description.setMaximumHeight(80)
        self.icon = QComboBox()
        self.icon.addItems(["organization", "business", "school", "folder", "home"])
        self.color = QComboBox()
        self.color.addItems(["#2563eb", "#16a34a", "#7c3aed", "#ea580c", "#dc2626"])
        self.template = QComboBox()
        self.template.addItems(["EMPTY", "PERSONAL", "STUDENT", "BUSINESS"])
        self.profile = QComboBox()
        for code in ("PERSONAL", "STUDENT", "BUSINESS", "EMPTY"):
            self.profile.addItem(self.feature_policy.PROFILE_NAMES[code], code)
        self.storage_plan = QComboBox()
        self.storage_plan.addItem("Pessoal — 10 GB", "PERSONAL_10GB")
        self.storage_plan.addItem("Estudante — 20 GB", "STUDENT_20GB")
        self.storage_plan.addItem("Empresarial — 60 GB", "BUSINESS_60GB")
        self.activate = QComboBox()
        self.activate.addItems(["Não ativar agora", "Ativar após criar"])

        if organization:
            self.icon.setCurrentText(organization.icon or "organization")
            self.color.setCurrentText(organization.color or "#2563eb")
            profile_code = getattr(organization, "profile_code", organization.template_code)
            self.profile.setCurrentIndex(max(0, self.profile.findData(profile_code)))
        else:
            profile_code = str(self.profile.currentData())

        form.addRow("Nome:", self.name)
        form.addRow("Descrição:", self.description)
        form.addRow("Ícone:", self.icon)
        form.addRow("Cor:", self.color)
        if show_template:
            form.addRow("Template:", self.template)
            form.addRow("Plano:", self.storage_plan)
            form.addRow("Após criar:", self.activate)
        form.addRow("Perfil de recursos:", self.profile)
        root.addLayout(form)

        self.resources = QLabel()
        self.resources.setWordWrap(True)
        root.addWidget(self.resources)
        feature_group = QGroupBox("Recursos habilitados para a organização")
        feature_layout = QVBoxLayout(feature_group)
        self.feature_checks: dict[str, QCheckBox] = {}
        for code, feature in self.feature_policy.FEATURES.items():
            check = QCheckBox(feature.name)
            check.setToolTip(feature.description)
            feature_layout.addWidget(check)
            self.feature_checks[code] = check
        root.addWidget(feature_group, 1)

        self._initial_enabled = (
            frozenset(enabled_features)
            if enabled_features is not None
            else self.feature_policy.default_enabled_codes(profile_code)
        )
        self._update_resources(initial=True)
        self.profile.currentIndexChanged.connect(self._update_resources)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self) -> dict:
        return {
            "name": self.name.text(),
            "description": self.description.toPlainText() or None,
            "icon": self.icon.currentText(),
            "color": self.color.currentText(),
            "template": self.template.currentText(),
            "profile_code": str(self.profile.currentData()),
            "storage_plan_code": str(self.storage_plan.currentData()),
            "activate": self.activate.currentIndex() == 1,
            "enabled_features": {
                code for code, check in self.feature_checks.items()
                if not check.isHidden() and check.isChecked()
            },
        }

    def _update_resources(self, _index=None, *, initial: bool = False) -> None:
        profile = self.feature_policy.for_profile(str(self.profile.currentData()))
        available = profile.codes
        selected = (
            self._initial_enabled
            if initial
            else self.feature_policy.default_enabled_codes(profile.profile_code)
        )
        for code, check in self.feature_checks.items():
            check.setVisible(code in available)
            check.setChecked(code in selected if code in available else False)
        self.resources.setText(
            "O perfil define o que está disponível; os itens marcados ficam ativos nesta organização."
        )
