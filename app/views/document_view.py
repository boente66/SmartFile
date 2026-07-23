from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.document_model import DocumentModel
from app.ui.icon_provider import IconProvider
from app.views.widgets.document_details_widget import DocumentDetailsWidget


class DocumentView(QWidget):
    import_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    filter_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()
    document_selected = pyqtSignal(int)
    open_requested = pyqtSignal(int)
    convert_requested = pyqtSignal(int)
    pdf_tools_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    favorite_requested = pyqtSignal(int)
    organization_changed = pyqtSignal(int)
    create_organization_requested = pyqtSignal()
    edit_organization_requested = pyqtSignal()
    delete_organization_requested = pyqtSignal()
    folder_selected = pyqtSignal(object)
    create_folder_requested = pyqtSignal()
    rename_folder_requested = pyqtSignal()
    delete_folder_requested = pyqtSignal()
    scope_changed = pyqtSignal(str)
    scanner_requested = pyqtSignal()
    visualize_requested = pyqtSignal(int)
    sign_requested = pyqtSignal(int)
    cloud_provider_changed = pyqtSignal(str)
    add_cloud_account_requested = pyqtSignal()
    sync_now_requested = pyqtSignal()
    pause_sync_requested = pyqtSignal()
    resume_sync_requested = pyqtSignal()
    disconnect_cloud_requested = pyqtSignal()
    cloud_history_requested = pyqtSignal()
    cloud_login_requested = pyqtSignal(str)
    cloud_oauth_settings_requested = pyqtSignal()
    copy_requested = pyqtSignal(int)
    paste_requested = pyqtSignal()
    restore_requested = pyqtSignal(int)
    permanent_delete_requested = pyqtSignal(int)
    empty_trash_requested = pyqtSignal()
    recalculate_storage_requested = pyqtSignal()
    largest_files_requested = pyqtSignal()
    change_storage_plan_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("documentsView")
        self._compact = False
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("documentsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        root.addWidget(self.scroll_area)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("documentsScrollContent")
        self.main_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.scroll_content)
        self.main_layout.setContentsMargins(18, 16, 18, 16)
        self.main_layout.setSpacing(12)
        self.scroll_area.setWidget(self.scroll_content)

        # Left column: header, controls, actions, table
        left = QWidget()
        left.setObjectName("documentsListPanel")
        self.list_panel = left
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        organization_row = QHBoxLayout()
        organization_row.addWidget(QLabel("Organização"))
        self.organization_combo = QComboBox()
        self.organization_combo.setObjectName("organizationSelector")
        self.organization_combo.setFixedWidth(360)
        self.organization_combo.currentIndexChanged.connect(self._emit_organization)
        organization_row.addWidget(self.organization_combo)
        self.btn_new_organization = self._icon_button("Nova organização", "organization_add")
        self.btn_edit_organization = self._icon_button("Editar organização", "edit")
        self.btn_delete_organization = self._icon_button("Excluir organização", "action_trash")
        self.btn_new_organization.clicked.connect(self.create_organization_requested.emit)
        self.btn_edit_organization.clicked.connect(self.edit_organization_requested.emit)
        self.btn_delete_organization.clicked.connect(self.delete_organization_requested.emit)
        organization_row.addWidget(self.btn_new_organization)
        organization_row.addWidget(self.btn_edit_organization)
        organization_row.addWidget(self.btn_delete_organization)
        organization_row.addStretch(1)
        left_layout.addLayout(organization_row)

        cloud_row = QHBoxLayout()
        cloud_row.addWidget(QLabel("Camada de Nuvem"))
        self.cloud_combo = QComboBox()
        self.cloud_combo.addItem("Local", "LOCAL")
        self.cloud_combo.addItem("OneDrive", "ONEDRIVE")
        self.cloud_combo.addItem("Google Drive", "GOOGLE_DRIVE")
        self.cloud_combo.currentIndexChanged.connect(self._emit_cloud_provider)
        cloud_row.addWidget(self.cloud_combo)
        self.btn_add_cloud = QPushButton("Adicionar Conta")
        self.btn_add_cloud.setObjectName("cloudAccountButton")
        IconProvider.apply(self.btn_add_cloud, "cloud_add")
        self.btn_add_cloud.clicked.connect(self.add_cloud_account_requested.emit)
        cloud_account_menu=QMenu(self.btn_add_cloud)
        cloud_account_menu.addAction("Microsoft OneDrive",lambda:self.cloud_login_requested.emit("ONEDRIVE"))
        cloud_account_menu.addAction("Google Drive",lambda:self.cloud_login_requested.emit("GOOGLE_DRIVE"))
        self.btn_add_cloud.setMenu(cloud_account_menu)
        cloud_row.addWidget(self.btn_add_cloud)
        self.btn_configure_provider = QPushButton("Configurar provedor")
        self.btn_configure_provider.setObjectName("configureCloudProviderButton")
        IconProvider.apply(self.btn_configure_provider, "provider_settings")
        self.btn_configure_provider.clicked.connect(self.cloud_oauth_settings_requested.emit)
        self.btn_configure_provider.setVisible(False)
        cloud_row.addWidget(self.btn_configure_provider)
        self.cloud_status_label = QLabel("Armazenamento local")
        self.cloud_status_label.setObjectName("cloudStatusLabel")
        cloud_row.addWidget(self.cloud_status_label)
        cloud_row.addStretch(1)
        left_layout.addLayout(cloud_row)

        storage_row = QHBoxLayout()
        self.storage_label = QLabel("Armazenamento: carregando…")
        self.storage_label.setObjectName("storageUsageLabel")
        self.storage_label.setWordWrap(True)
        self.storage_progress = QProgressBar()
        self.storage_progress.setRange(0, 100)
        self.storage_progress.setTextVisible(True)
        self.storage_progress.setMaximumWidth(260)
        self.btn_manage_storage = QPushButton("Gerenciar armazenamento")
        IconProvider.apply(self.btn_manage_storage, "folder")
        storage_menu = QMenu(self.btn_manage_storage)
        storage_menu.addAction("Abrir lixeira", lambda: self._select_scope("trash"))
        storage_menu.addAction("Recalcular uso", self.recalculate_storage_requested.emit)
        storage_menu.addAction("Ver arquivos maiores", self.largest_files_requested.emit)
        storage_menu.addAction("Alterar plano", self.change_storage_plan_requested.emit)
        storage_menu.addAction("Sincronizar agora", self.sync_now_requested.emit)
        storage_menu.addAction("Ver erros da nuvem", self.cloud_history_requested.emit)
        self.btn_manage_storage.setMenu(storage_menu)
        storage_row.addWidget(self.storage_label)
        storage_row.addWidget(self.storage_progress)
        storage_row.addWidget(self.btn_manage_storage)
        storage_row.addStretch(1)
        left_layout.addLayout(storage_row)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        self.document_toolbar_buttons = []
        action_specs = (
            ("Novo", "new", self.create_folder_requested.emit),
            ("Importar", "import", self.import_requested.emit),
            ("Abrir", "viewer_open", lambda: self._emit_for_selected(self.open_requested)),
            ("Scanner", "scanner", self.scanner_requested.emit),
            ("Visualizar", "visualize", lambda: self._emit_for_selected(self.visualize_requested)),
            ("PDF Tools", "pdf", lambda: self._emit_for_selected(self.pdf_tools_requested)),
            ("Converter", "converter", lambda: self._emit_for_selected(self.convert_requested)),
            ("Assinar", "sign", lambda: self._emit_for_selected(self.sign_requested)),
            ("Favorito", "action_star", lambda: self._emit_for_selected(self.favorite_requested)),
            ("Excluir", "action_trash", lambda: self._emit_for_selected(self.delete_requested)),
            ("Mais", "more", lambda: None),
            ("Sincronizar", "cloud_sync", lambda: None),
        )
        for text, icon, callback in action_specs:
            widget = self._icon_button(text, icon)
            widget.setProperty("actionText", text)
            widget.setText(text)
            widget.setMinimumSize(72, 52)
            widget.setMaximumSize(16777215, 52)
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            widget.clicked.connect(callback)
            actions.addWidget(widget)
            self.document_toolbar_buttons.append(widget)
            if text == "Importar":
                self.btn_import = widget
            if text == "Sincronizar":
                self.btn_sync = widget
        sync_menu = QMenu(self.btn_sync)
        sync_menu.addAction("Sincronizar Agora", self.sync_now_requested.emit)
        sync_menu.addAction("Pausar", self.pause_sync_requested.emit)
        sync_menu.addAction("Retomar", self.resume_sync_requested.emit)
        sync_menu.addSeparator()
        sync_menu.addAction("Conectar conta", self.add_cloud_account_requested.emit)
        sync_menu.addAction("Remover conta/login", self.disconnect_cloud_requested.emit)
        sync_menu.addAction("Histórico", self.cloud_history_requested.emit)
        sync_menu.addSeparator()
        self.oauth_settings_action = sync_menu.addAction(
            "Configurar provedor", self.cloud_oauth_settings_requested.emit
        )
        self.oauth_settings_action.setVisible(False)
        self.btn_sync.setMenu(sync_menu)
        actions.addStretch(1)
        left_layout.addLayout(actions)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por nome, categoria ou tags")
        self.search_edit.textChanged.connect(self._emit_search)
        search_row.addWidget(QLabel("Buscar"))
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(QLabel("Tipo"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Todos", "PDF", "DOCX", "SPREADSHEET", "IMAGE", "TEXT", "OTHER"])
        self.type_combo.currentTextChanged.connect(self._emit_filter)
        self.type_combo.setFixedWidth(140)
        search_row.addWidget(self.type_combo)
        left_layout.addLayout(search_row)

        self.status_label = QLabel("Nenhum documento importado")
        self.status_label.setObjectName("documentCount")
        left_layout.addWidget(self.status_label)

        self.documents_table = QTableWidget(0, 6)
        self.documents_table.setHorizontalHeaderLabels(["Nome", "Tipo", "Categoria", "Tamanho", "Favorito", "Nuvem"])
        self.documents_table.setAlternatingRowColors(True)
        self.documents_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.documents_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.documents_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.documents_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.documents_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.documents_table.setMinimumHeight(280)
        self.documents_table.verticalHeader().setVisible(False)
        header = self.documents_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self.documents_table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.documents_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.documents_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.documents_table.customContextMenuRequested.connect(self._show_document_context_menu)
        browser = QSplitter(Qt.Orientation.Horizontal)
        browser.setObjectName("documentBrowserSplitter")
        folders_panel = QFrame()
        folders_panel.setObjectName("foldersPanel")
        folders_layout = QVBoxLayout(folders_panel)
        folders_layout.setContentsMargins(10, 10, 10, 10)
        navigation = (
            ("Documentos", "documents", "documents"),
            ("Favoritos", "action_star", "favorites"),
            ("Recentes", "recent", "recent"),
            ("Pastas", "folder", "folders"),
            ("Lixeira", "action_trash", "trash"),
        )
        self.scope_buttons = {}
        for text, icon, scope in navigation:
            nav_button = QPushButton(text)
            nav_button.setObjectName("documentNavigationButton")
            nav_button.setCheckable(True)
            IconProvider.apply(nav_button, icon)
            nav_button.clicked.connect(lambda _checked=False, value=scope: self._select_scope(value))
            folders_layout.addWidget(nav_button)
            self.scope_buttons[scope] = nav_button
        self.scope_buttons["documents"].setChecked(True)
        self.btn_empty_trash=QPushButton("Esvaziar lixeira"); IconProvider.apply(self.btn_empty_trash,"action_trash"); self.btn_empty_trash.clicked.connect(self.empty_trash_requested.emit); self.btn_empty_trash.hide(); folders_layout.addWidget(self.btn_empty_trash)
        folders_header = QHBoxLayout()
        folders_header.addWidget(QLabel("Pastas"))
        folders_header.addStretch()
        self.btn_new_folder = self._icon_button("Nova pasta", "folder_add")
        self.btn_rename_folder = self._icon_button("Renomear pasta", "edit")
        self.btn_delete_folder = self._icon_button("Excluir pasta", "action_trash")
        self.btn_new_folder.clicked.connect(self.create_folder_requested.emit)
        self.btn_rename_folder.clicked.connect(self.rename_folder_requested.emit)
        self.btn_delete_folder.clicked.connect(self.delete_folder_requested.emit)
        folders_header.addWidget(self.btn_new_folder)
        folders_header.addWidget(self.btn_rename_folder)
        folders_header.addWidget(self.btn_delete_folder)
        folders_layout.addLayout(folders_header)
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.currentItemChanged.connect(self._emit_folder)
        folders_layout.addWidget(self.folder_tree, 1)
        browser.addWidget(folders_panel)
        browser.addWidget(self.documents_table)
        browser.setSizes([220, 720])
        browser.setCollapsible(0, True)
        left_layout.addWidget(browser, 1)
        self.browser_splitter = browser

        self.details = DocumentDetailsWidget()
        self.details.open_requested.connect(self.open_requested.emit)
        self.details.convert_requested.connect(self.convert_requested.emit)
        self.details.pdf_tools_requested.connect(self.pdf_tools_requested.emit)
        self.details.trash_requested.connect(self.delete_requested.emit)
        self.details.favorite_requested.connect(self.favorite_requested.emit)

        # Compatibilidade para consumidores que referenciam as ações públicas.
        self.btn_open = self.details.btn_open
        self.btn_convert = self.details.btn_convert
        self.btn_pdf = self.details.btn_pdf
        self.btn_delete = self.details.btn_trash
        self.btn_favorite = self.details.btn_favorite

        self.main_layout.addWidget(left, 3)
        self.main_layout.addWidget(self.details, 1)
        self._set_document_actions_enabled(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_compact_layout(event.size().width() < 1500)
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width > 0:
            # O conteúdo deve se reorganizar verticalmente, nunca criar uma
            # rolagem horizontal por diferenças de métricas entre plataformas.
            self.scroll_content.setFixedWidth(viewport_width)

    def _apply_compact_layout(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        self.main_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        )
        if compact:
            self.details.setMinimumHeight(460)
            self.main_layout.setStretch(0, 0)
            self.main_layout.setStretch(1, 0)
        else:
            self.details.setMinimumHeight(0)
            self.main_layout.setStretch(0, 3)
            self.main_layout.setStretch(1, 1)
        for button in self.document_toolbar_buttons:
            if compact:
                button.setText("")
                button.setFixedSize(38, 38)
            else:
                button.setText(str(button.property("actionText")))
                button.setMinimumSize(72, 52)
                button.setMaximumSize(16777215, 52)
        self.scroll_content.updateGeometry()

    def set_documents(self, documents: list[DocumentModel]):
        self.documents_table.setRowCount(len(documents))
        for row_index, document in enumerate(documents):
            self.documents_table.setItem(row_index, 0, QTableWidgetItem(document.name))
            self.documents_table.setItem(row_index, 1, QTableWidgetItem(document.file_type or ""))
            self.documents_table.setItem(row_index, 2, QTableWidgetItem(document.category or ""))
            self.documents_table.setItem(row_index, 3, QTableWidgetItem(self._format_size(document.size)))
            self.documents_table.setItem(row_index, 4, QTableWidgetItem("★" if document.favorite else ""))
            self.documents_table.setItem(row_index, 5, QTableWidgetItem(self._cloud_label(document)))

            for column in range(self.documents_table.columnCount()):
                self.documents_table.item(row_index, column).setData(Qt.ItemDataRole.UserRole, document.id)

        self.documents_table.resizeRowsToContents()

    def set_organizations(self, organizations, active_id: int) -> None:
        self.organization_combo.blockSignals(True)
        self.organization_combo.clear()
        active_index = 0
        for index, organization in enumerate(organizations):
            self.organization_combo.addItem(organization.name, organization.id)
            if organization.id == active_id:
                active_index = index
        self.organization_combo.setCurrentIndex(active_index)
        self.organization_combo.blockSignals(False)

    def set_folders(self, organization_name: str, folders) -> None:
        self.folder_tree.blockSignals(True)
        self.folder_tree.clear()
        root = QTreeWidgetItem([organization_name])
        root.setData(0, Qt.ItemDataRole.UserRole, None)
        root.setIcon(0, IconProvider.icon("organization"))
        self.folder_tree.addTopLevelItem(root)
        items = {}
        for folder in folders:
            item = QTreeWidgetItem([folder.name])
            item.setData(0, Qt.ItemDataRole.UserRole, folder.id)
            item.setIcon(0, IconProvider.icon("folder"))
            items[folder.id] = item
        for folder in folders:
            parent = items.get(folder.parent_id, root)
            parent.addChild(items[folder.id])
        root.setExpanded(True)
        self.folder_tree.setCurrentItem(root)
        self.folder_tree.expandAll()
        self.folder_tree.blockSignals(False)
        self.folder_selected.emit(None)

    def set_cloud_settings(self, settings, account=None, oauth_state=None) -> None:
        self.cloud_combo.blockSignals(True)
        index = self.cloud_combo.findData(settings.sync_mode)
        self.cloud_combo.setCurrentIndex(max(0, index))
        self.cloud_combo.blockSignals(False)
        state = getattr(oauth_state, "value", oauth_state)
        if state == "NOT_CONFIGURED":
            text = "Integração não configurada pelo administrador"
        elif state == "AUTHENTICATING":
            text = "Autenticando…"
        elif state == "TOKEN_EXPIRED":
            text = "Autorização expirada — conecte novamente"
        elif state == "REAUTH_REQUIRED":
            text = "Nova autenticação necessária"
        elif state == "ERROR":
            text = "Erro na conexão da nuvem"
        elif state == "DISABLED":
            text = "Nuvem indisponível para este perfil"
        elif settings.sync_mode == "LOCAL":
            text = "Armazenamento local"
        elif settings.paused:
            text = f"{settings.sync_mode} — pausado"
        elif account:
            text = account.display_name or account.email or settings.sync_mode
        else:
            text = f"{settings.sync_mode} — conta necessária"
        if settings.last_sync:
            text += f" · última sincronização {settings.last_sync}"
        self.cloud_status_label.setText(text)

    def apply_cloud_permissions(self, context) -> None:
        can_view = context is None or context.has_permission("cloud.view")
        can_connect = context is None or context.has_permission("cloud.connect")
        can_sync = context is None or context.has_permission("cloud.sync")
        can_configure = context is not None and context.is_system_admin()
        self.cloud_combo.setVisible(can_view)
        self.cloud_status_label.setVisible(can_view)
        self.btn_add_cloud.setVisible(can_view and can_connect)
        self.btn_sync.setVisible(can_view and can_sync)
        self.oauth_settings_action.setVisible(can_configure)
        self.btn_configure_provider.setVisible(can_configure)

    def set_storage_usage(self, summary) -> None:
        used = self._format_gb(summary.used_bytes)
        quota = self._format_gb(summary.quota_bytes)
        reserved = self._format_gb(summary.reserved_bytes)
        available = self._format_gb(summary.available_bytes)
        local_free = self._format_gb(summary.local_free_bytes)
        self.storage_label.setText(
            f"{summary.plan_name}: {used} de {quota} · reservado {reserved} · disponível {available} "
            f"· disco livre {local_free} · {summary.level}"
        )
        self.storage_progress.setValue(round(summary.percent))
        self.storage_progress.setFormat(f"{summary.percent:.1f}% — {summary.level}")
        self.storage_progress.setAccessibleName(
            f"Uso do armazenamento {summary.percent:.1f} por cento, estado {summary.level}"
        )

    def selected_folder_id(self) -> int | None:
        item = self.folder_tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def _select_scope(self, scope: str) -> None:
        self._current_scope=scope
        for name, button in self.scope_buttons.items():
            button.setChecked(name == scope)
        self.folder_tree.setVisible(scope in {"documents", "folders"})
        self.btn_empty_trash.setVisible(scope=="trash")
        self.scope_changed.emit(scope)

    def show_document_details(self, document: DocumentModel | None):
        self.details.set_document(document)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def current_search(self) -> str:
        return self.search_edit.text().strip()

    def current_type_filter(self) -> str:
        return self.type_combo.currentText()

    def selected_document_id(self) -> int | None:
        selected = self.documents_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        item = self.documents_table.item(row, 0)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole) or 0) or None

    def _emit_search(self, text: str):
        self.search_requested.emit(text)

    def _on_selection_changed(self):
        document_id = self.selected_document_id()
        self._set_document_actions_enabled(document_id is not None)
        if document_id is not None:
            self.document_selected.emit(document_id)

    def _set_document_actions_enabled(self, enabled: bool):
        self.details.set_actions_enabled(enabled)

    def _emit_filter(self, value: str):
        self.filter_requested.emit(value)

    def _emit_organization(self, index: int) -> None:
        organization_id = self.organization_combo.itemData(index)
        if organization_id is not None:
            self.organization_changed.emit(int(organization_id))

    def _emit_cloud_provider(self, index: int) -> None:
        provider = self.cloud_combo.itemData(index)
        if provider:
            self.cloud_provider_changed.emit(str(provider))

    def _emit_folder(self, current, _previous) -> None:
        self.folder_selected.emit(
            current.data(0, Qt.ItemDataRole.UserRole) if current else None
        )

    def _emit_for_selected(self, signal) -> None:
        document_id = self.selected_document_id()
        if document_id is not None:
            signal.emit(document_id)

    def _show_document_context_menu(self,position):
        menu=QMenu(self); document_id=self.selected_document_id(); trash=getattr(self,"_current_scope","documents")=="trash"
        if document_id is not None:
            menu.addAction("Copiar",lambda:self.copy_requested.emit(document_id))
            if trash:
                menu.addAction("Restaurar",lambda:self.restore_requested.emit(document_id)); menu.addAction("Excluir definitivamente",lambda:self.permanent_delete_requested.emit(document_id))
            else: menu.addAction("Mover para lixeira",lambda:self.delete_requested.emit(document_id))
        menu.addAction("Colar",self.paste_requested.emit)
        if trash: menu.addSeparator(); menu.addAction("Esvaziar lixeira",self.empty_trash_requested.emit)
        menu.exec(self.documents_table.viewport().mapToGlobal(position))

    @staticmethod
    def _icon_button(text: str, icon: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("documentToolbarButton")
        button.setToolTip(text)
        button.setAccessibleName(text)
        button.setFixedSize(38, 38)
        IconProvider.apply(button, icon)
        return button

    def _emit_open(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.open_requested.emit(document_id)

    def _emit_convert(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.convert_requested.emit(document_id)

    def _emit_pdf_tools(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.pdf_tools_requested.emit(document_id)

    def _emit_delete(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.delete_requested.emit(document_id)

    def _emit_favorite(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.favorite_requested.emit(document_id)

    def _format_size(self, size: int | None) -> str:
        if size is None:
            return ""
        units = ["B", "KB", "MB", "GB"]
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.0f} {unit}"
            value /= 1024
        return f"{value:.0f} GB"

    @staticmethod
    def _format_gb(size: int) -> str:
        value = max(0, int(size)) / (1024 ** 3)
        return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " GB"

    @staticmethod
    def _cloud_label(document: DocumentModel) -> str:
        labels = {
            "LOCAL_ONLY": "🖥 Local", "PENDING_UPLOAD": "⟳ Pendente",
            "UPLOADING": "⟳ Sincronizando", "SYNCED": f"☁ {document.cloud_provider or 'Nuvem'}",
            "PENDING_DOWNLOAD": "⟳ Baixando", "CONFLICT": "⚠ Conflito",
            "ERROR": "⚠ Erro", "SYNC_ERROR": "⚠ Erro", "REMOTE_DELETED": "⚠ Removido na nuvem",
            "LOCAL_DELETED": "🗑 Removido localmente",
        }
        return labels.get(document.cloud_status, document.cloud_status)
