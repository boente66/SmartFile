from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
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
    rename_document_requested = pyqtSignal(int)
    smart_filters_changed = pyqtSignal(object)
    configure_transport_requested = pyqtSignal()
    document_requests_requested = pyqtSignal()
    audit_history_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("documentsView")
        self._compact = False
        self._context = None
        self._feature_set = None
        self._responsive_rows: list[QBoxLayout] = []
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
        self.profile_badge = QLabel("Perfil: Essencial")
        self.profile_badge.setObjectName("organizationProfileBadge")
        organization_row.addWidget(self.profile_badge)
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
        self._responsive_rows.append(organization_row)

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
        self._responsive_rows.append(cloud_row)

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
        self._responsive_rows.append(storage_row)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        self.document_toolbar_buttons = []
        self.action_buttons = {}
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
            self.action_buttons[text] = widget
            if text == "Importar":
                self.btn_import = widget
            if text == "Sincronizar":
                self.btn_sync = widget
            if text == "Mais":
                self.btn_more = widget
        self.more_menu = QMenu(self.btn_more)
        self.more_copy_action = self.more_menu.addAction(
            IconProvider.icon("copy"), "Copiar",
            lambda: self._emit_for_selected(self.copy_requested),
        )
        self.more_paste_action = self.more_menu.addAction(
            IconProvider.icon("paste"), "Colar", self.paste_requested.emit,
        )
        self.more_rename_action = self.more_menu.addAction(
            IconProvider.icon("edit"), "Renomear",
            lambda: self._emit_for_selected(self.rename_document_requested),
        )
        self.more_trash_action = self.more_menu.addAction(
            IconProvider.icon("action_trash"), "Mover para lixeira",
            lambda: self._emit_for_selected(self.delete_requested),
        )
        self.more_copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.more_paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.more_rename_action.setShortcut(QKeySequence(Qt.Key.Key_F2))
        self.more_trash_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        for action in (
            self.more_copy_action,
            self.more_paste_action,
            self.more_rename_action,
            self.more_trash_action,
        ):
            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.more_menu.addSeparator()
        self.enterprise_menu = self.more_menu.addMenu("Recursos empresariais")
        self.enterprise_menu.setIcon(IconProvider.icon("business"))
        self.transport_action = self.enterprise_menu.addAction(
            IconProvider.icon("provider_settings"), "Configurar transporte",
            self.configure_transport_requested.emit,
        )
        self.requests_action = self.enterprise_menu.addAction(
            IconProvider.icon("documents"), "Solicitações e prazos",
            self.document_requests_requested.emit,
        )
        self.audit_action = self.enterprise_menu.addAction(
            IconProvider.icon("history"), "Histórico auditável",
            self.audit_history_requested.emit,
        )
        self.more_menu.aboutToShow.connect(self._update_more_menu)
        self.btn_more.setMenu(self.more_menu)
        self.btn_more.setToolTip("Mais ações — clique para abrir o menu contextual")
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
        self._responsive_rows.append(search_row)
        self.smart_filters_widget = QWidget()
        smart_filters = QHBoxLayout(self.smart_filters_widget)
        smart_filters.setContentsMargins(0, 0, 0, 0)
        smart_filters.addWidget(QLabel("Filtros rápidos"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("Todas as origens", None)
        for label, value in (
            ("Importação", "IMPORT"), ("Scanner", "SCANNER"),
            ("Conversor", "CONVERTER"), ("Nuvem", "CLOUD_DOWNLOAD"),
            ("Assinatura", "DIGITAL_SIGNATURE"),
        ):
            self.source_combo.addItem(label, value)
        self.source_combo.currentIndexChanged.connect(self._emit_smart_filters)
        smart_filters.addWidget(self.source_combo)
        self.period_combo = QComboBox()
        self.period_combo.addItem("Qualquer período", None)
        self.period_combo.addItem("Últimos 7 dias", 7)
        self.period_combo.addItem("Últimos 30 dias", 30)
        self.period_combo.addItem("Últimos 90 dias", 90)
        self.period_combo.currentIndexChanged.connect(self._emit_smart_filters)
        smart_filters.addWidget(self.period_combo)
        self.favorite_combo = QComboBox()
        self.favorite_combo.addItem("Todos", None)
        self.favorite_combo.addItem("Somente favoritos", True)
        self.favorite_combo.addItem("Sem favorito", False)
        self.favorite_combo.currentIndexChanged.connect(self._emit_smart_filters)
        smart_filters.addWidget(self.favorite_combo)
        smart_filters.addStretch(1)
        left_layout.addWidget(self.smart_filters_widget)
        self._responsive_rows.append(smart_filters)

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
        self._setup_document_shortcuts()
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
        self._update_more_menu()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Mantém lista e detalhes lado a lado em notebooks comuns; o empilhamento
        # é reservado a janelas realmente estreitas.
        self._apply_compact_layout(event.size().width() < 1050)
        # O QScrollArea com widgetResizable acompanha o viewport. Um fixedWidth
        # calculado durante o primeiro layout congelava o conteúdo em ~640 px
        # mesmo depois de maximizar a janela.
        self.scroll_content.setMinimumWidth(0)
        self.scroll_content.setMaximumWidth(16777215)

    def _apply_compact_layout(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        self.main_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        )
        row_direction = (
            QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        )
        for row in self._responsive_rows:
            row.setDirection(row_direction)
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
        self._context = context
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
        can_import = context is None or context.has_permission("document.import")
        can_update = context is None or context.has_permission("document.update")
        can_folder = context is None or context.has_permission("folder.create")
        can_organization = context is None or context.has_permission("organization.update")
        self.btn_import.setEnabled(can_import)
        self.action_buttons["Excluir"].setEnabled(can_update)
        self.btn_new_folder.setEnabled(can_folder)
        self.btn_rename_folder.setEnabled(can_folder)
        self.btn_delete_folder.setEnabled(can_folder)
        self.btn_edit_organization.setEnabled(can_organization)
        self.btn_delete_organization.setEnabled(can_organization)
        self.transport_action.setEnabled(
            context is None or context.has_permission("transport.configure")
        )
        self.requests_action.setEnabled(
            context is None or context.has_permission("document.request.view")
        )
        self.audit_action.setEnabled(
            context is None or context.has_permission("audit.view")
        )
        self._update_more_menu()

    def apply_profile_features(self, feature_set) -> None:
        self._feature_set = feature_set
        self.profile_badge.setText(f"Perfil: {feature_set.profile_name}")
        indexed = feature_set.has("indexed_filters")
        self.smart_filters_widget.setVisible(indexed)
        self.transport_action.setVisible(feature_set.has("server_transport"))
        self.requests_action.setVisible(feature_set.has("document_requests"))
        self.audit_action.setVisible(feature_set.has("audit_history"))
        self.enterprise_menu.menuAction().setVisible(
            feature_set.profile_code == "BUSINESS"
            and any((
                feature_set.has("server_transport"),
                feature_set.has("document_requests"),
                feature_set.has("audit_history"),
            ))
        )
        self.action_buttons["Assinar"].setVisible(feature_set.has("digital_signature"))
        if not feature_set.has("cloud_sync"):
            self.cloud_combo.setCurrentIndex(0)
            self.cloud_combo.setEnabled(False)
            self.btn_add_cloud.setVisible(False)
            self.btn_sync.setVisible(False)
        else:
            self.cloud_combo.setEnabled(True)

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
        self._update_more_menu()
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
        self._update_more_menu()
        if document_id is not None:
            self.document_selected.emit(document_id)

    def _set_document_actions_enabled(self, enabled: bool):
        self.details.set_actions_enabled(enabled)

    def _emit_filter(self, value: str):
        self.filter_requested.emit(value)
        self._emit_smart_filters()

    def _emit_smart_filters(self, *_args) -> None:
        self.smart_filters_changed.emit({
            "file_type": self.type_combo.currentText(),
            "source_type": self.source_combo.currentData(),
            "period_days": self.period_combo.currentData(),
            "favorite": self.favorite_combo.currentData(),
        })

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
        can_update = self._context is None or self._context.has_permission("document.update")
        can_create = self._context is None or self._context.has_permission("document.create")
        if document_id is not None:
            copy_action = menu.addAction(IconProvider.icon("copy"),"Copiar",lambda:self.copy_requested.emit(document_id))
            copy_action.setShortcut(QKeySequence.StandardKey.Copy)
            if trash:
                menu.addAction(IconProvider.icon("restore"),"Restaurar",lambda:self.restore_requested.emit(document_id)).setEnabled(can_update)
                delete_action = menu.addAction(IconProvider.icon("action_trash"),"Excluir definitivamente",lambda:self.permanent_delete_requested.emit(document_id))
                delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
                delete_action.setEnabled(can_update)
            else:
                rename_action = menu.addAction(IconProvider.icon("edit"),"Renomear",lambda:self.rename_document_requested.emit(document_id))
                rename_action.setShortcut(QKeySequence(Qt.Key.Key_F2))
                rename_action.setEnabled(can_update)
                delete_action = menu.addAction(IconProvider.icon("action_trash"),"Mover para lixeira",lambda:self.delete_requested.emit(document_id))
                delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
                delete_action.setEnabled(can_update)
        paste_action = menu.addAction(IconProvider.icon("paste"),"Colar",self.paste_requested.emit)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.setEnabled(can_create)
        if trash: menu.addSeparator(); menu.addAction(IconProvider.icon("action_trash"),"Esvaziar lixeira",self.empty_trash_requested.emit).setEnabled(can_update)
        menu.exec(self.documents_table.viewport().mapToGlobal(position))

    def _setup_document_shortcuts(self) -> None:
        """Instala atalhos somente na tabela para não capturar edição em campos de texto."""
        bindings = (
            ("copy", QKeySequence.StandardKey.Copy, self._copy_selected),
            ("paste", QKeySequence.StandardKey.Paste, self._paste_from_keyboard),
            ("rename", QKeySequence(Qt.Key.Key_F2), self._rename_from_keyboard),
            ("delete", QKeySequence(Qt.Key.Key_Delete), self._delete_from_keyboard),
            ("context", QKeySequence("Shift+F10"), self._show_keyboard_context_menu),
            ("menu", QKeySequence(Qt.Key.Key_Menu), self._show_keyboard_context_menu),
        )
        self.document_shortcuts = {}
        for name, sequence, callback in bindings:
            shortcut = QShortcut(sequence, self.documents_table)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self.document_shortcuts[name] = shortcut

    def _copy_selected(self) -> None:
        self._emit_for_selected(self.copy_requested)

    def _paste_from_keyboard(self) -> None:
        if self._context is None or self._context.has_permission("document.create"):
            self.paste_requested.emit()

    def _rename_from_keyboard(self) -> None:
        can_update = self._context is None or self._context.has_permission("document.update")
        if can_update and getattr(self, "_current_scope", "documents") != "trash":
            self._emit_for_selected(self.rename_document_requested)

    def _delete_from_keyboard(self) -> None:
        document_id = self.selected_document_id()
        can_update = self._context is None or self._context.has_permission("document.update")
        if document_id is None or not can_update:
            return
        if getattr(self, "_current_scope", "documents") == "trash":
            self.permanent_delete_requested.emit(document_id)
        else:
            self.delete_requested.emit(document_id)

    def _show_keyboard_context_menu(self) -> None:
        index = self.documents_table.currentIndex()
        position = (
            self.documents_table.visualRect(index).center()
            if index.isValid()
            else self.documents_table.viewport().rect().center()
        )
        self._show_document_context_menu(position)

    def _update_more_menu(self) -> None:
        selected = self.selected_document_id() is not None
        can_update = self._context is None or self._context.has_permission("document.update")
        can_create = self._context is None or self._context.has_permission("document.create")
        trash = getattr(self, "_current_scope", "documents") == "trash"
        self.more_copy_action.setEnabled(selected)
        self.more_paste_action.setEnabled(can_create)
        self.more_rename_action.setEnabled(selected and can_update and not trash)
        self.more_trash_action.setEnabled(selected and can_update and not trash)

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
