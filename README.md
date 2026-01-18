# Claude Usage Monitor - GNOME Extension

A GNOME Shell extension that displays your Claude Code usage (session and weekly remaining) in the top panel.

## Requirements

- GNOME Shell 45 or later (uses ESM modules)
- Claude Code CLI installed and authenticated

## Installation

### Option 1: Manual Installation

1. Copy the extension to your GNOME extensions directory:

```bash
mkdir -p ~/.local/share/gnome-shell/extensions/
cp -r claude-usage@local ~/.local/share/gnome-shell/extensions/
```

2. Restart GNOME Shell:
   - On X11: Press `Alt+F2`, type `r`, press Enter
   - On Wayland: Log out and log back in

3. Enable the extension:

```bash
gnome-extensions enable claude-usage@local
```

### Option 2: Using gnome-extensions-cli

```bash
# If you have gnome-extensions-cli installed
gnome-extensions install claude-usage@local/
gnome-extensions enable claude-usage@local
```

## Usage

Once enabled, you'll see a robot emoji (🤖) with a percentage in your top panel. This shows your remaining weekly Claude usage.

Click on it to see:
- Session remaining percentage
- Weekly remaining percentage
- Last update time
- Manual refresh button

The extension automatically refreshes every 5 minutes.

## Configuration

To change the refresh interval, edit `extension.js` and modify:

```javascript
const REFRESH_INTERVAL_SECONDS = 300; // Change to desired seconds
```

## Troubleshooting

### "Error" shown in panel

1. Make sure `claude` CLI is installed and in your PATH
2. Check that you're authenticated with Claude Code
3. Look at GNOME Shell logs: `journalctl -f -o cat /usr/bin/gnome-shell`

### Extension not appearing

1. Verify the extension is enabled: `gnome-extensions list --enabled`
2. Check for errors: `gnome-extensions info claude-usage@local`

### Usage not parsing correctly

The extension tries to parse percentage values from the `/usage` command output. If Claude changes their output format, the parsing logic in `_parseUsage()` may need updating.

## How it Works

The extension runs `fetch_usage.sh` which:
1. Locates the Claude CLI
2. Runs `claude -p "/usage"` to get usage info non-interactively
3. Returns the output for parsing

The extension then parses the output looking for percentage values and displays the remaining usage.

## Uninstalling

```bash
gnome-extensions disable claude-usage@local
rm -rf ~/.local/share/gnome-shell/extensions/claude-usage@local
```
