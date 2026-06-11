# fd_dev

macOS SwiftUI app with a bundled Python backend for label layout previewing, generation workflows, file imports, history, and package tracking utilities.

## Repository layout

- `swift/` — native macOS Swift Package app.
- `python/` — source Python backend.
- `swift/vendor/backend/` — backend copy bundled with the macOS app.
- `scripts/` — maintenance and CI validation scripts.
- `docs/` — implementation notes and app audits.

## Latest main-branch improvements

The current `main` branch includes the most recent preview/layout reliability work:

- Live label preview guide overlays.
- Configurable UPS template mask support.
- UPS template mask documentation in `docs/ups-template-mask.md`.
- App improvement audit in `docs/app-improvement-audit.md`.
- GitHub Actions CI for Swift and Python validation.
- Backend mirror validation scripts.
- `.env.example` for local environment configuration.

## Development checks

Run the Swift build from the Swift package directory:

```bash
cd swift
swift build --disable-sandbox
```

Validate Python syntax and mirrored backend files:

```bash
python -m compileall python swift/vendor/backend scripts
python scripts/check_backend_sync.py
python scripts/check_vendor_sync.py
```

## Backend mirroring rule

Some backend files exist in both `python/` and `swift/vendor/backend/`. When editing backend behavior, update both copies or CI will fail. Use the scripts above before pushing.

## UPS template mask

The UPS white rectangle/mask is configurable through `label_layout.ups.template_mask`. The original mask location was:

```text
x_position = 0
y_position = 585
width = 405
height = 375
right edge = 405
bottom edge = 960
```

See `docs/ups-template-mask.md` for details.

## Settings and generated data

The app stores runtime settings/history/output outside the app bundle. Do not commit local settings, generated labels, barcodes, logs, or environment files.

## Environment configuration

Optional integrations should use environment variables or a local `.env` file. Do not commit API keys or user-specific tokens.

See `.env.example` for supported environment names.
