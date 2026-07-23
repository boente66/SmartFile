# SmartFile

SmartFile is a cross-platform desktop application for local document management, file conversion, PDF editing, document scanning, and a lightweight Mini GED experience. It is designed to keep your documents organized and accessible without depending on cloud services.

## ✨ Main features

- Import and organize documents locally
- Search, filter, favorites, and recent history
- Convert between common document formats
- Edit and manage PDF files
- Scan documents from compatible devices
- Work with a lightweight local Mini GED based on SQLite
- Optionally mirror each organization's logical folders and documents through
  the Cloud Layer to OneDrive or Google Drive
- Create full ZIP backups as system administrator, with confirmation and checksums

## 🖼️ Screenshots

Screenshots will be added in the folder below as the interface evolves:

- [assets/screenshots](assets/screenshots)

## 🛠️ Technologies

- Python 3.12
- PyQt6 for the desktop interface
- SQLite for local persistence
- PyMuPDF, pypdf, reportlab, Pillow
- python-docx, openpyxl, pandas

### Run the application

```bash
python run.py
```

> On Linux, scanner support may require additional system packages depending on your environment.

## Linux beta package

The first Linux beta is distributed for compatible amd64 systems based on
Linux Mint, Ubuntu, and Debian. Install a generated artifact with:

> This package is a non-official beta prototype for testing. Keep independent
> backups and report any problems found through the project's issue tracker.

```bash
sudo apt install ./smartfile_0.9.0~beta1_amd64.deb
```

Start it from the applications menu or with `smartfile`. Remove only the
application with `sudo apt remove smartfile`. Package removal intentionally
preserves the database, documents, settings, and backups in the user's data
directories. See [Linux beta notes](docs/BETA_LINUX.md) for build instructions,
optional system integrations, known limitations, and complete data-removal
guidance.

## Windows experimental package

The Windows x64 onedir bundle and Inno Setup installer are generated on an
official GitHub Actions Windows runner. Open **Actions > Windows beta package**,
run the workflow manually, and download its temporary artifact. Builds are not
published as a final release automatically.

See [the Windows beta test guide](docs/GUIA_TESTE_WINDOWS_BETA.md) before
distribution. This is an experimental, non-certified build and still requires
manual validation on real Windows 10 or 11 hardware.

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
