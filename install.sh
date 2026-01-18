#!/bin/bash
# Install Claude Usage Monitor GNOME Extension

set -e

EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions"
EXTENSION_UUID="claude-usage@local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Claude Usage Monitor extension..."

# Create extensions directory if it doesn't exist
mkdir -p "$EXTENSION_DIR"

# Remove old installation if present
if [ -d "$EXTENSION_DIR/$EXTENSION_UUID" ]; then
    echo "Removing previous installation..."
    rm -rf "$EXTENSION_DIR/$EXTENSION_UUID"
fi

# Copy extension files
echo "Copying extension files..."
cp -r "$SCRIPT_DIR/$EXTENSION_UUID" "$EXTENSION_DIR/"

# Check GNOME version and use appropriate extension.js
GNOME_VERSION=$(gnome-shell --version 2>/dev/null | grep -oP '\d+' | head -1)
if [ -n "$GNOME_VERSION" ] && [ "$GNOME_VERSION" -lt 45 ]; then
    echo "Detected GNOME $GNOME_VERSION (< 45), using legacy extension..."
    mv "$EXTENSION_DIR/$EXTENSION_UUID/extension.js" "$EXTENSION_DIR/$EXTENSION_UUID/extension_modern.js"
    mv "$EXTENSION_DIR/$EXTENSION_UUID/extension_legacy.js" "$EXTENSION_DIR/$EXTENSION_UUID/extension.js"
else
    echo "Using modern extension (GNOME 45+)..."
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Restart GNOME Shell:"
echo "   - X11: Press Alt+F2, type 'r', press Enter"
echo "   - Wayland: Log out and log back in"
echo ""
echo "2. Enable the extension:"
echo "   gnome-extensions enable $EXTENSION_UUID"
echo ""
echo "Or use GNOME Extensions app to enable it."
