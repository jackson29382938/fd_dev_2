#!/usr/bin/env bash
# Build and launch the FTID macOS app entirely from the swift/ folder.
#
# This script is fully self-contained:
#   * Swift sources are read from ./Sources
#   * The Python backend that the Swift app drives is read from ./vendor/backend
#   * site-packages can come from ./vendor/python-site-packages,
#     ./venv_build, or a system Python 3.13 install (in that order).
#
# The only external requirements are:
#   * A working `swift` toolchain (Xcode / Command Line Tools)
#   * A Python 3.13 framework (for the bundled runtime) – set
#     FTID_PYTHON_FRAMEWORK to override the default
#     /Library/Frameworks/Python.framework path
#   * Python site-packages – either pre-populated in
#     swift/vendor/python-site-packages or installed in the chosen fallback
#     (use script/install_python_deps.sh to populate it from the system venv)

set -euo pipefail

MODE="${1:-run}"
APP_NAME="FTIDMacApp"
DISPLAY_NAME="FTID Generator"
BUNDLE_ID="com.ftid.macapp"
MIN_SYSTEM_VERSION="14.0"

# Always operate relative to this script so it works from any cwd.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_HOME="${HOME}"

# Normalize source after recent layout-settings edits so older local checkouts and
# partially-applied pulls do not fail with known Swift compile errors. Also make
# layout generation explicit without leaking generate_label-only payload access
# into shared batch/regeneration helpers.
normalize_swift_sources() {
  local settings_view="$ROOT_DIR/Sources/FTIDMacApp/Views/SettingsView.swift"
  local label_preview="$ROOT_DIR/Sources/FTIDMacApp/Views/LabelPreviewView.swift"
  local app_models="$ROOT_DIR/Sources/FTIDMacApp/Models/AppModels.swift"
  local bridge_script="$ROOT_DIR/vendor/backend/bridge/ftid_bridge.py"

  if [[ -f "$settings_view" ]]; then
    /usr/bin/perl -0pi -e 's/\.foregroundStyle\(\.accent\)/.foregroundColor(.accentColor)/g' "$settings_view"
    /usr/bin/perl -0pi -e 's/@ViewBuilder content: \(\) -> Content/@ViewBuilder content: @escaping () -> Content/g' "$settings_view"
  fi

  if [[ -f "$label_preview" ]]; then
    /usr/bin/perl -0pi -e 's/import AppKit\nimport SwiftUI/import AppKit\nimport CoreText\nimport SwiftUI/' "$label_preview"
    python3 - "$label_preview" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text()

# Root cause fix: the native preview renderer was anchoring each glyph with its
# own bounding-box minY and adding a transparent canvas margin. Large one-line
# text therefore appeared lower in preview even when its stored Y was correct.
text = text.replace('var lineHeights: [CGFloat] = []', 'var lineMetrics: [(height: CGFloat, maxY: CGFloat)] = []')
text = text.replace('var maxY: CGFloat = 0\n            var minY: CGFloat = 0', 'var maxY: CGFloat = -.greatestFiniteMagnitude\n            var minY: CGFloat = .greatestFiniteMagnitude')
text = text.replace('lineHeights.append(height)', 'lineMetrics.append((height: height, maxY: maxY))')
text = text.replace('let canvasWidth = max(1, maxWidth + 12)\n        let canvasHeight = max(1, totalHeight + 12)', 'let canvasWidth = max(1, maxWidth)\n        let canvasHeight = max(1, totalHeight)')
text = text.replace('let lineHeight = lineHeights[index]\n            var xPos: CGFloat = 0', 'let metrics = lineMetrics[index]\n            let baselineY = canvasHeight - yOffset - metrics.maxY\n            var xPos: CGFloat = 0')
text = re.sub(r'\n\s*var rect = CGRect\.zero\n\s*CTFontGetBoundingRectsForGlyphs\(font, \.default, &glyph, &rect, 1\)', '', text)
text = text.replace(
'''                let advance = CTFontGetAdvancesForGlyphs(font, .default, &glyph, nil, 1)
                lineWidth += advance + charSpacing * scale
                maxY = max(maxY, rect.maxY)''',
'''                var rect = CGRect.zero
                CTFontGetBoundingRectsForGlyphs(font, .default, &glyph, &rect, 1)
                let advance = CTFontGetAdvancesForGlyphs(font, .default, &glyph, nil, 1)
                lineWidth += advance + charSpacing * scale
                maxY = max(maxY, rect.maxY)'''
)
text = text.replace('.translatedBy(x: xPos, y: canvasHeight - yOffset - lineHeight + rect.minY)', '.translatedBy(x: xPos, y: baselineY)')
text = text.replace('yOffset += lineHeight', 'yOffset += metrics.height')
path.write_text(text)
PY
  fi

  if [[ -f "$app_models" ]]; then
    /usr/bin/perl -0pi -e 's/\n\s*typealias TextBlock = LabelLayout\.CarrierLayout\.TextBlock\n/\n/g' "$app_models"
    /usr/bin/perl -0pi -e 's/"address_type": form\.addressType\.rawValue,\n\s*\]/"address_type": form.addressType.rawValue,\n                    "label_layout": self.labelLayoutJSONObject(),\n                ]/g' "$app_models"
    /usr/bin/perl -0pi -e 'if ($_ !~ /private func labelLayoutJSONObject\(\) -> \[String: Any\]/) { s/\n    private func refreshCollections\(\) async throws \{/\n    private func labelLayoutJSONObject() -> [String: Any] {\n        let encoder = JSONEncoder()\n        encoder.outputFormatting = [.sortedKeys]\n        guard let data = try? encoder.encode(settings.labelLayout),\n              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {\n            return [:]\n        }\n        return object\n    }\n\n    private func refreshCollections() async throws {/ }' "$app_models"
  fi

  if [[ -f "$bridge_script" ]]; then
    python3 - "$bridge_script" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text()

bad = 'label_layout = payload.get("label_layout") or payload.get("layout_overrides") or settings.get("label_layout", {})'
base = 'label_layout = settings.get("label_layout", {})'

# Repair older bad normalization. _finalize_label_generation has no payload;
# import_process/regenerate both flow through it, so this must stay settings-only.
text = text.replace(bad, base)

# Only handle_generate_label has a request payload. It may receive live layout
# JSON from Swift; otherwise it falls back to persisted settings.
pattern = r'(def handle_generate_label\(payload: Dict\[str, Any\]\).*?\n)    label_layout = settings\.get\("label_layout", \{\}\)'
replacement = r'\1    label_layout = payload.get("label_layout") or payload.get("layout_overrides") or settings.get("label_layout", {})'
text = re.sub(pattern, replacement, text, flags=re.S)
path.write_text(text)
PY
  fi
}

normalize_swift_sources

# Everything we need lives inside the swift/ folder – no ../python lookup.
VENDOR_DIR="$ROOT_DIR/vendor"
BACKEND_SRC="$VENDOR_DIR/backend"
ICON_SOURCE="$VENDOR_DIR/app_icon.icns"

DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_FRAMEWORKS="$APP_CONTENTS/Frameworks"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"

# Default Python framework – can be overridden via env var.
PYTHON_FRAMEWORK_SRC="${FTID_PYTHON_FRAMEWORK:-/Library/Frameworks/Python.framework}"
PYTHON_SITE_PACKAGES=""
CREDENTIALS_SRC=""

# Search order for site-packages:
#   1. FTID_PYTHON_SITE_PACKAGES env var (explicit override)
#   2. swift/vendor/python-site-packages    (ship it with the project)
#   3. swift/venv_build/...                 (per-project venv)
#   4. /Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages
SITE_PACKAGES_CANDIDATES=(
  "${FTID_PYTHON_SITE_PACKAGES:-}"
  "$VENDOR_DIR/python-site-packages"
  "$ROOT_DIR/venv_build/lib/python3.13/site-packages"
  "/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages"
)

for candidate in "${SITE_PACKAGES_CANDIDATES[@]}"; do
  if [[ -n "${candidate}" && -d "${candidate}" ]]; then
    PYTHON_SITE_PACKAGES="$candidate"
    break
  fi
done

CREDENTIALS_CANDIDATES=(
  "${FTID_CREDENTIALS_PATH:-}"
  "${GOOGLE_APPLICATION_CREDENTIALS:-}"
  "$BACKEND_SRC/requirements/credentials.json"
  "$ROOT_DIR/credentials.json"
  "$USER_HOME/.ftid/credentials.json"
  "$USER_HOME/Documents/FTID_Generator/credentials.json"
)

for candidate in "${CREDENTIALS_CANDIDATES[@]}"; do
  if [[ -n "${candidate}" && -f "${candidate}" ]]; then
    CREDENTIALS_SRC="$candidate"
    break
  fi
done

if [[ -z "$PYTHON_SITE_PACKAGES" ]]; then
  echo "Could not find Python site-packages." >&2
  echo "Set FTID_PYTHON_SITE_PACKAGES, populate $VENDOR_DIR/python-site-packages," >&2
  echo "or create $ROOT_DIR/venv_build with the project requirements." >&2
  echo "Tip: run script/install_python_deps.sh to do this automatically." >&2
  exit 1
fi

if [[ ! -d "$PYTHON_FRAMEWORK_SRC" ]]; then
  echo "Python framework not found at $PYTHON_FRAMEWORK_SRC" >&2
  echo "Install Python 3.13 from python.org or set FTID_PYTHON_FRAMEWORK." >&2
  exit 1
fi

if [[ ! -d "$BACKEND_SRC" ]]; then
  echo "Vendored backend missing at $BACKEND_SRC" >&2
  echo "Re-run script/sync_from_python.sh or restore vendor/backend/." >&2
  exit 1
fi

# Clean and build the Swift executable.
rm -rf "$DIST_DIR"
mkdir -p "$APP_MACOS" "$APP_RESOURCES" "$APP_FRAMEWORKS"

swift build --disable-sandbox -c release
cp ".build/release/$APP_NAME" "$APP_BINARY"

# Bundle backend and runtime assets.
cp -R "$BACKEND_SRC" "$APP_RESOURCES/backend"
if [[ -d "$PYTHON_SITE_PACKAGES" ]]; then
  mkdir -p "$APP_RESOURCES/python-site-packages"
  cp -R "$PYTHON_SITE_PACKAGES"/. "$APP_RESOURCES/python-site-packages/"
fi
if [[ -d "$PYTHON_FRAMEWORK_SRC" ]]; then
  cp -R "$PYTHON_FRAMEWORK_SRC" "$APP_FRAMEWORKS/Python.framework"
fi

# Copy optional credentials into the backend requirements folder if present.
if [[ -n "$CREDENTIALS_SRC" ]]; then
  mkdir -p "$APP_RESOURCES/backend/requirements"
  cp "$CREDENTIALS_SRC" "$APP_RESOURCES/backend/requirements/credentials.json"
fi

if [[ -f "$ICON_SOURCE" ]]; then
  cp "$ICON_SOURCE" "$APP_RESOURCES/app_icon.icns"
fi

cat > "$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleName</key><string>$DISPLAY_NAME</string>
  <key>CFBundleDisplayName</key><string>$DISPLAY_NAME</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>$MIN_SYSTEM_VERSION</string>
  <key>NSHighResolutionCapable</key><true/>
PLIST

if [[ -f "$APP_RESOURCES/app_icon.icns" ]]; then
  cat >> "$INFO_PLIST" <<PLIST
  <key>CFBundleIconFile</key><string>app_icon</string>
PLIST
fi

cat >> "$INFO_PLIST" <<PLIST
</dict>
</plist>
PLIST

chmod +x "$APP_BINARY"
echo "Built $APP_BUNDLE"

if [[ "$MODE" == "run" ]]; then
  open "$APP_BUNDLE"
fi
