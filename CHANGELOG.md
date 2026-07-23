# Changelog

## [Unreleased]

- Added organization-scoped remote roots and logical-folder mapping
- Added idempotent folder creation to the common OneDrive/Google Drive contract
- Added remote reconciliation for folder create, rename, move, and delete
- Added queued document moves and safe mapping reset when changing cloud accounts
- Clarified that SQLite remains local and is covered by the administrative ZIP backup

## [0.9.0-beta.1] - 2026-07-15

- Added a reproducible PyInstaller onedir build for Linux amd64
- Added Debian package integration, desktop entry, and hicolor icons
- Centralized read-only resource resolution for source and frozen execution
- Added package validation, isolated smoke tests, and SHA-256 generation
- Documented external integrations and beta limitations
- Added administrator-only full ZIP backup with confirmation, SQLite snapshot,
  file manifest, checksums, audit history, and background execution

## [0.8.0] - 2026-07-10

- Initial desktop workflow for conversion, PDF tools, scanner, and local Mini GED
- Local persistence with SQLite
- PyQt6-based interface
