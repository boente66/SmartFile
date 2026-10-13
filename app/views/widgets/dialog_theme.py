"""Tema explícito para diálogos de importação com ancestrais escuros."""

def apply_import_theme(dialog):
    dialog.setStyleSheet('''
        QDialog { background: #f7f9fb; color: #172033; }
        QLabel, QCheckBox { color: #172033; background: transparent; }
        QLabel#errorLabel { color: #b42318; }
        QLineEdit, QTextEdit, QComboBox, QDateEdit, QListWidget, QTreeWidget {
            background: #ffffff; color: #172033; border: 1px solid #cbd5e1;
            selection-background-color: #1769e8; selection-color: #ffffff;
        }
        QPushButton { background: #ffffff; color: #172033; border: 1px solid #cbd5e1; padding: 7px; }
        QPushButton:disabled { color: #64748b; background: #eef2f6; }
    ''')
