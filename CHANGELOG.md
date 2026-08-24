# Changelog

## [Unreleased]

- Fixed duplicate and overlapping cards in the LAN device dialog during
  repeated discovery refreshes, with a compact scrollable layout
- Added contextual viewing of received PDFs through the official PDF Viewer
- Added visual receipt signatures from drawing or normalized image input
- Added atomic acknowledgement receipt PDFs with UUID, SHA-256 and schema 20
- Added persistent reverse receipt delivery with peer validation and retry

## [0.9.0-beta.3] - 2026-08-22

- Redesigned the Documents workspace while preserving controllers, services,
  repositories, signals, permissions, storage, and cloud synchronization contracts
- Added a unified organization, cloud, and storage header with a compact action bar
- Added collapsible indexed filters, logical-folder breadcrumbs, panel visibility
  controls, document-type icons, modified timestamps, and contextual status feedback
- Centralized the Delivery/LAN protocol version in a neutral module
- Added structured and safe HTTP 409/500 responses to the LAN identity endpoint
- Retained schema 18 without creating a migration
- Added logical-folder navigation, search, persistent multi-selection, and safe
  storage-path hiding to the delivery basket document picker
- Added non-blocking mDNS/DNS-SD discovery for SmartFile LAN installations with
  explicit authorization, UUID/protocol handshake, connection tests, and manual fallback
- Added a revision-aware in-app notice so existing beta installations receive
  the update alert without changing the public beta version
- Added the integrated Captura e PDF workspace for scanner acquisition, image
  import, PDF composition, persistent rotation, drag-and-drop ordering, export,
  and managed GED import without intermediate files
- Preserved Scanner and PDF Tools services and legacy route aliases while
  consolidating their primary navigation entry
- Added real filesystem-based NAS transport with a dedicated persistent queue
- Added atomic chunked uploads, SHA-256 verification, cooperative cancellation,
  bounded retry, recovery, and organization-isolated remote roots
- Added background processing and administrative NAS connection testing
- Added transport audit events and durable delete jobs after permanent trash removal
- Added immutable transport targets so historical retries and deletes keep their
  original NAS after an endpoint change
- Added conservative reconciliation for legacy jobs whose physical target cannot
  be proven
- Added OS Credential Vault integration through keyring with opaque database refs,
  safe rotation, in-use protection, and database-failure compensation
- Added incremental database migration 17 without changing the public beta version

## [0.9.0-beta.2] - 2026-08-07

- Separated profile capabilities from organization-enabled features
- Added conservative BUSINESS defaults with independent activation of cloud,
  corporate transport, document requests, and deadline timers
- Added schema migration 15 and auditable organization feature settings
- Centralized profile and feature updates in the organization administration service
- Hardened NAS, LAN, and HTTPS transport authorization and endpoint validation
- Added active-member assignees and independent deadlines to document requests
- Added a non-blocking, once-per-version in-app release notification
- Preserved the Cloud Layer, document shortcuts, trash, scanner, PDF tools, and storage

- Separated organization feature profiles from initial folder templates
- Added PERSONAL, STUDENT, BUSINESS, and EMPTY capability policies
- Added indexed document filters, multi-term metadata search, and safe rename
- Added left-click contextual actions through the More menu
- Added keyboard access with Ctrl+C, Ctrl+V, F2, Delete, Shift+F10 and Menu
- Added a logical-folder explorer for multi-file document imports
- Added audited BUSINESS transport configuration for NAS, HTTPS, and LAN
- Added BUSINESS document requests with deadlines and status tracking
- Fixed the Documents view width being frozen after the first layout pass
- Redesigned the converter workflow with compatible-format filtering, output
  validation, cooperative cancellation, session history, and Linux
  LibreOffice support
- Added offline password recovery with expiring, one-time Argon2id-protected codes
- Added recovery-code regeneration and session revocation after password reset
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
