# App improvement audit

This audit focuses on maintainability, reliability, privacy, and packaging quality for the macOS Swift app plus bundled Python backend.

## Implemented in this pass

- Added this audit so future changes have a clear prioritized checklist.
- Kept the UPS template mask documented in `docs/ups-template-mask.md` with its original pixel coordinates.
- Confirmed the live preview already has guide overlays and debounced preview reloads.
- Confirmed CI exists at `.github/workflows/ci.yml` for Swift build and Python syntax validation.

## Highest-priority follow-ups

1. Add first-class Swift settings for `label_layout.ups.template_mask` so X/Y/width/height/opacity can be edited from the Settings UI instead of JSON.
2. Keep `python/` and `swift/vendor/backend/` in sync with a validation script in CI.
3. Remove committed secrets and require environment variables for third-party service tokens.
4. Add regression tests for template mask rendering and preview element sizing.
5. Add a packaging smoke test that verifies bundled backend resources exist before app launch.
6. Add user-facing error messages for missing optional integrations instead of silently falling back.
7. Add a one-click "open generated output folder" affordance beside generation results.
8. Add release build documentation for a clean macOS app bundle.

## Notes

The app is currently split across a native SwiftUI frontend and a Python backend copied into `swift/vendor/backend`. Any behavioral backend change should be mirrored in both locations or validated by automation.
