# SmartFile

SmartFile is a cross-platform desktop application for local document management, file conversion, PDF editing, document scanning, and a lightweight Mini GED experience. It is designed to keep your documents organized and accessible without depending on cloud services.

## ✨ Main features

- Import and organize documents locally
- Search, filter, favorites, and recent history
- Convert between common document formats
- Edit and manage PDF files
- Scan documents from compatible devices
- Work with a lightweight local Mini GED based on SQLite

## 🖼️ Screenshots

Screenshots will be added in the folder below as the interface evolves:

- [assets/screenshots](assets/screenshots)

## 🛠️ Technologies

- Python 3.10+
- PyQt6 for the desktop interface
- SQLite for local persistence
- PyMuPDF, pypdf, reportlab, Pillow
- python-docx, openpyxl, pandas


```

### Run the application

```bash
python run.py
```

> On Linux, scanner support may require additional system packages depending on your environment.

## 📁 Project structure

```text
SmartFile/
├── app/
├── assets/
├── docs/
├── requirements.txt
├── LICENSE
├── README.md
├── CHANGELOG.md
└── .gitignore
```

## 🗺️ Roadmap

- v0.8: UI stabilization and persistence improvements
- v0.9: richer PDF and scanner workflows
- v1.0: polished release candidate with packaged installers

## 🤝 Contributing

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a branch for your change
3. Commit your improvements
4. Open a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

## 🏷️ Suggested GitHub topics

- python
- pyqt6
- pdf
- scanner
- document-management
- mini-ged
- desktop
- qt
- document-converter
- sqlite

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
