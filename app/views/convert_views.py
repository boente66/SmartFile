from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.icon_provider import IconProvider


class ConvertView(QWidget):
    """Interface responsiva do Conversor, sem executar regras de domínio."""

    convert_requested = pyqtSignal(dict)
    cancel_requested = pyqtSignal()
    input_path_changed = pyqtSignal(str)
    open_output_requested = pyqtSignal(str)
    return_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("convertView")
        self._busy = False
        self._output_manually_selected = False
        self._started_at = 0.0
        self._history_rows: list[QWidget] = []
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("convertScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        content = QWidget()
        content.setObjectName("convertContent")
        scroll.setWidget(content)
        outer.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(26, 22, 26, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Conversão de Arquivos")
        title.setObjectName("convertTitle")
        subtitle = QLabel(
            "Converta documentos, planilhas, imagens e PDFs com segurança."
        )
        subtitle.setObjectName("convertSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.btn_return = QPushButton("Voltar aos documentos")
        self.btn_return.setObjectName("secondary")
        IconProvider.apply(self.btn_return, "documents")
        self.btn_return.clicked.connect(self.return_requested.emit)
        header.addWidget(self.btn_return)
        layout.addLayout(header)

        setup_card = self._card("Configurar conversão")
        setup_layout = setup_card.layout()

        setup_layout.addWidget(self._field_label("Arquivo de entrada"))
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(
            "Selecione PDF, DOCX, imagem, planilha, CSV ou TXT"
        )
        self.input_edit.editingFinished.connect(
            lambda: self.input_path_changed.emit(
                self.input_edit.text().strip()
            )
        )
        input_row.addWidget(self.input_edit, 1)
        self.btn_input = QPushButton("Abrir")
        IconProvider.apply(self.btn_input, "open")
        self.btn_input.clicked.connect(self._browse_input)
        input_row.addWidget(self.btn_input)
        setup_layout.addLayout(input_row)
        self.input_hint = QLabel("Nenhum arquivo selecionado")
        self.input_hint.setObjectName("convertHint")
        self.input_hint.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        setup_layout.addWidget(self.input_hint)

        setup_layout.addWidget(self._field_label("Formato de saída"))
        self.format_combo = QComboBox()
        self.format_combo.setPlaceholderText(
            "Selecione primeiro um arquivo compatível"
        )
        self.format_combo.currentIndexChanged.connect(
            self._on_format_changed
        )
        setup_layout.addWidget(self.format_combo)

        setup_layout.addWidget(self._field_label("Arquivo de saída"))
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "O destino será sugerido automaticamente"
        )
        self.output_edit.textChanged.connect(self._update_convert_enabled)
        self.output_edit.textEdited.connect(
            lambda: setattr(self, "_output_manually_selected", True)
        )
        output_row.addWidget(self.output_edit, 1)
        self.btn_output = QPushButton("Salvar como")
        IconProvider.apply(self.btn_output, "save")
        self.btn_output.clicked.connect(self._browse_output)
        output_row.addWidget(self.btn_output)
        setup_layout.addLayout(output_row)

        self.btn_convert = QPushButton("Converter arquivo")
        self.btn_convert.setObjectName("convertPrimary")
        IconProvider.apply(self.btn_convert, "converter")
        self.btn_convert.setMinimumHeight(44)
        self.btn_convert.clicked.connect(self._request_conversion)
        setup_layout.addWidget(self.btn_convert)
        layout.addWidget(setup_card)

        progress_card = self._card("Progresso da conversão")
        progress_layout = progress_card.layout()
        progress_header = QHBoxLayout()
        self.progress_file = QLabel("Aguardando uma conversão")
        self.progress_file.setObjectName("convertProgressFile")
        progress_header.addWidget(self.progress_file, 1)
        self.elapsed_label = QLabel("Tempo: 00:00")
        self.elapsed_label.setObjectName("convertHint")
        progress_header.addWidget(self.elapsed_label)
        progress_layout.addLayout(progress_header)
        self.progress_message = QLabel(
            "Escolha um arquivo e um formato para começar."
        )
        self.progress_message.setObjectName("convertHint")
        progress_layout.addWidget(self.progress_message)
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_row.addWidget(self.progress_bar, 1)
        self.progress_percent = QLabel("0%")
        self.progress_percent.setObjectName("convertProgressPercent")
        progress_row.addWidget(self.progress_percent)
        progress_layout.addLayout(progress_row)
        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_open_output = QPushButton("Abrir resultado")
        IconProvider.apply(self.btn_open_output, "open")
        self.btn_open_output.setVisible(False)
        actions.addWidget(self.btn_open_output)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("convertCancel")
        IconProvider.apply(self.btn_cancel, "cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        actions.addWidget(self.btn_cancel)
        progress_layout.addLayout(actions)
        layout.addWidget(progress_card)

        history_card = self._card("Histórico recente")
        self.history_layout = history_card.layout()
        self.history_empty = QLabel(
            "As conversões concluídas nesta sessão aparecerão aqui."
        )
        self.history_empty.setObjectName("convertHint")
        self.history_layout.addWidget(self.history_empty)
        layout.addWidget(history_card)
        layout.addStretch()
        self._update_convert_enabled()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("convertFieldLabel")
        return label

    @staticmethod
    def _card(title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("convertCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(9)
        heading = QLabel(title)
        heading.setObjectName("convertSectionTitle")
        layout.addWidget(heading)
        return frame

    def set_input_path(self, path: str) -> None:
        self.input_edit.setText(path)
        self._output_manually_selected = False
        self.input_hint.setText(path or "Nenhum arquivo selecionado")
        self.input_path_changed.emit(path)

    def set_available_formats(
        self, source_format: str, targets: tuple[str, ...]
    ) -> None:
        previous = self.format_combo.currentData()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for target in targets:
            self.format_combo.addItem(
                f"{source_format} → {target}", target
            )
        if previous in targets:
            self.format_combo.setCurrentIndex(
                self.format_combo.findData(previous)
            )
        elif targets:
            self.format_combo.setCurrentIndex(0)
        self.format_combo.blockSignals(False)
        self.format_combo.setEnabled(bool(targets) and not self._busy)
        if targets:
            self.input_hint.setText(self.input_edit.text().strip())
            self._on_format_changed()
        else:
            self.output_edit.clear()
            value = self.input_edit.text().strip()
            self.input_hint.setText(
                "Formato de entrada não suportado"
                if value else "Nenhum arquivo selecionado"
            )
        self._update_convert_enabled()

    def set_output_path(self, path: str, *, manual: bool = False) -> None:
        self._output_manually_selected = manual
        self.output_edit.setText(path)

    def current_target(self) -> str:
        return str(self.format_combo.currentData() or "")

    def set_busy(self, busy: bool, input_path: str = "") -> None:
        self._busy = busy
        for widget in (
            self.input_edit,
            self.btn_input,
            self.output_edit,
            self.btn_output,
            self.format_combo,
        ):
            widget.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        self.btn_return.setEnabled(not busy)
        if busy:
            self.progress_file.setText(Path(input_path).name)
            self.progress_bar.setValue(0)
            self.progress_percent.setText("0%")
            self.progress_message.setText("Preparando conversão...")
            self.btn_open_output.setVisible(False)
            self._started_at = time.monotonic()
            self._elapsed_timer.start()
        else:
            self._elapsed_timer.stop()
        self._update_convert_enabled()

    def update_progress(self, value: int, message: str) -> None:
        value = max(0, min(100, int(value)))
        self.progress_bar.setValue(value)
        self.progress_percent.setText(f"{value}%")
        self.progress_message.setText(message)

    def show_success(self, output_path: str) -> None:
        self.set_busy(False)
        self.update_progress(100, "Conversão concluída com sucesso")
        self.btn_open_output.setVisible(True)
        try:
            self.btn_open_output.clicked.disconnect()
        except TypeError:
            pass
        self.btn_open_output.clicked.connect(
            lambda: self.open_output_requested.emit(output_path)
        )

    def show_failure(self, message: str) -> None:
        self.set_busy(False)
        self.progress_message.setText(message)
        self.progress_percent.setText("Erro")

    def show_cancelled(self) -> None:
        self.set_busy(False)
        self.progress_message.setText("Conversão cancelada")
        self.progress_percent.setText("Cancelado")

    def show_cancelling(self) -> None:
        self.btn_cancel.setEnabled(False)
        self.progress_message.setText(
            "Cancelando com segurança; aguarde a etapa atual terminar..."
        )

    def add_history(
        self, input_name: str, conversion: str, output_path: str
    ) -> None:
        self.history_empty.setVisible(False)
        row = QFrame()
        row.setObjectName("convertHistoryRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        icon = QLabel("✓")
        icon.setObjectName("convertHistorySuccess")
        layout.addWidget(icon)
        text = QLabel(f"{input_name}\n{conversion}  •  Concluído")
        text.setObjectName("convertHistoryText")
        layout.addWidget(text, 1)
        button = QPushButton("Abrir")
        IconProvider.apply(button, "open")
        button.clicked.connect(
            lambda: self.open_output_requested.emit(output_path)
        )
        layout.addWidget(button)
        self.history_layout.insertWidget(1, row)
        self._history_rows.insert(0, row)
        while len(self._history_rows) > 5:
            old = self._history_rows.pop()
            self.history_layout.removeWidget(old)
            old.deleteLater()

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo",
            "",
            (
                "Arquivos compatíveis "
                "(*.pdf *.docx *.jpg *.jpeg *.png *.tif *.tiff "
                "*.xlsx *.csv *.txt);;Todos os arquivos (*)"
            ),
        )
        if path:
            self.set_input_path(path)

    def _browse_output(self) -> None:
        target = self.current_target().lower()
        if not target:
            return
        suggested = self.output_edit.text().strip()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar arquivo convertido",
            suggested,
            f"Arquivo {target.upper()} (*.{target})",
        )
        if path:
            selected = Path(path)
            if selected.suffix.lower() != f".{target}":
                selected = selected.with_suffix(f".{target}")
            self.set_output_path(str(selected), manual=True)

    def _on_format_changed(self) -> None:
        target = self.current_target().lower()
        input_value = self.input_edit.text().strip()
        if target and input_value and not self._output_manually_selected:
            source = Path(input_value)
            destination = source.with_name(
                f"{source.stem}_convertido.{target}"
            )
            self.output_edit.setText(str(destination))
        self._update_convert_enabled()

    def _request_conversion(self) -> None:
        self.convert_requested.emit({
            "input": self.input_edit.text().strip(),
            "output": self.output_edit.text().strip(),
            "target": self.current_target(),
            "format": self.format_combo.currentText(),
        })

    def _update_elapsed(self) -> None:
        elapsed = max(0, int(time.monotonic() - self._started_at))
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        value = (
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if hours else f"{minutes:02d}:{seconds:02d}"
        )
        self.elapsed_label.setText(f"Tempo: {value}")

    def _update_convert_enabled(self) -> None:
        enabled = bool(
            not self._busy
            and self.input_edit.text().strip()
            and self.output_edit.text().strip()
            and self.current_target()
        )
        self.btn_convert.setEnabled(enabled)
