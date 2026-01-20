#!/usr/bin/env python3
"""
Claude Usage System Tray - Windows taskbar utility
Shows Claude Code usage with AI-powered predictions.
"""

import sys
import time
import threading
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    import pystray
except ImportError:
    print("Please install required packages: pip install pystray pillow")
    sys.exit(1)

# Add parent directory to path for shared modules
SCRIPT_DIR = Path(__file__).parent.parent / "claude-usage@local"
sys.path.insert(0, str(SCRIPT_DIR))

from usage_fetcher import UsageFetcher, get_display_values

REFRESH_INTERVAL_SECONDS = 300  # 5 minutes


def create_icon_image(text="🤖", bg_color="#4A90D9"):
    """Create a simple icon with text."""
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw background circle
    draw.ellipse([4, 4, size-4, size-4], fill=bg_color)

    # Try to draw text (fallback to simple shapes if font fails)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        bbox = draw.textbbox((0, 0), text[:2], font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - 4
        draw.text((x, y), text[:2], fill="white", font=font)
    except:
        # Fallback: draw a simple robot face
        draw.rectangle([18, 20, 28, 30], fill='white')  # left eye
        draw.rectangle([36, 20, 46, 30], fill='white')  # right eye
        draw.rectangle([22, 38, 42, 44], fill='white')  # mouth

    return img


class ClaudeUsageTray:
    def __init__(self):
        self.running = True

        # Display state (updated from fetcher)
        self.data = None
        self.is_stale = False
        self.status = "Starting..."
        self.error = None
        self.last_successful = None

        # Create initial icon
        self.icon = pystray.Icon(
            "claude_usage",
            create_icon_image(),
            "Claude Usage: Loading...",
            menu=self.create_menu()
        )

        # Set up shared fetcher
        self.fetcher = UsageFetcher(on_update=self._on_fetcher_update)
        # Note: pystray doesn't need main thread scheduling for menu updates

        # Start refresh thread
        self.refresh_thread = threading.Thread(target=self.refresh_loop, daemon=True)
        self.refresh_thread.start()

    def _on_fetcher_update(self, state):
        """Called when fetcher state changes."""
        self.data = state['data']
        self.is_stale = state['is_stale']
        self.error = state['error']
        self.status = state['status']
        self.last_successful = state['last_successful_fetch']

        # Update tooltip
        self._update_tooltip()

    def _update_tooltip(self):
        """Update the system tray tooltip."""
        if self.data:
            v = get_display_values(self.data)
            robot = "[ZZZ]" if self.is_stale else ""
            warning = "[!] " if v['exhausts_before_reset'] else ""

            if v['time_remaining_str']:
                self.icon.title = f"{warning}{robot}Claude: {v['time_remaining_str']} ({v['session_remaining']}%)"
            else:
                self.icon.title = f"{robot}Claude: S:{v['session_remaining']}% W:{v['weekly_remaining']}%"
        else:
            self.icon.title = f"Claude Usage: {self.status}"

    def _get_display_values(self):
        """Get current display values."""
        return get_display_values(self.data)

    def get_account_text(self):
        v = self._get_display_values()
        if v['account_email']:
            text = f"Account: {v['account_email']}"
            if v['plan_type']:
                text += f" ({v['plan_type']})"
            return text
        return "Account: --"

    def get_session_text(self):
        v = self._get_display_values()
        stale = " (stale)" if self.is_stale else ""
        return f"Session: {v['session_remaining']}% remaining{stale}"

    def get_time_remaining_text(self):
        v = self._get_display_values()
        if v['time_remaining_str']:
            text = f"Depletes in ~{v['time_remaining_str']}"
            if v['confidence']:
                try:
                    conf = round(float(v['confidence']) * 100)
                    text += f" ({conf}% conf)"
                except:
                    pass
            if v['exhausts_before_reset']:
                text += " - before reset!"
            return text
        return "Depletes: --"

    def get_session_resets_text(self):
        v = self._get_display_values()
        if v['session_resets']:
            return f"Resets at {v['session_resets']}"
        return "Resets: --"

    def get_weekly_text(self):
        v = self._get_display_values()
        text = f"Weekly: {v['weekly_remaining']}% remaining"
        if v['extra_pct']:
            text += f" (Extra: {v['extra_pct']}% used)"
        return text

    def get_weekly_resets_text(self):
        v = self._get_display_values()
        if v['weekly_resets']:
            return f"Resets {v['weekly_resets']}"
        return "Resets: --"

    def get_last_updated_text(self):
        if self.last_successful:
            suffix = " (stale)" if self.is_stale else ""
            return f"Updated: {self.last_successful.strftime('%H:%M:%S')}{suffix}"
        return "Updated: Never"

    def get_status_text(self):
        return f"Status: {self.status}"

    def get_error_text(self):
        if self.error:
            return f"Last error: {self.error}"
        return "Last error: None"

    def create_menu(self):
        return pystray.Menu(
            pystray.MenuItem(lambda item: self.get_account_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: self.get_session_text(), None, enabled=False),
            pystray.MenuItem(lambda item: self.get_time_remaining_text(), None, enabled=False),
            pystray.MenuItem(lambda item: self.get_session_resets_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: self.get_weekly_text(), None, enabled=False),
            pystray.MenuItem(lambda item: self.get_weekly_resets_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: self.get_last_updated_text(), None, enabled=False),
            pystray.MenuItem(lambda item: self.get_status_text(), None, enabled=False),
            pystray.MenuItem(lambda item: self.get_error_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh Now", self.refresh_clicked),
            pystray.MenuItem("Quit", self.quit_clicked),
        )

    def refresh_clicked(self, icon, item):
        self.fetcher.fetch_async()

    def quit_clicked(self, icon, item):
        self.running = False
        icon.stop()

    def refresh_loop(self):
        # Initial fetch
        self.fetcher.fetch_async()

        while self.running:
            for _ in range(REFRESH_INTERVAL_SECONDS):
                if not self.running:
                    break
                time.sleep(1)
            if self.running:
                self.fetcher.fetch_async()

    def run(self):
        """Run the system tray app."""
        self.icon.run()


def main():
    print("Starting Claude Usage System Tray...")
    print("Look for the icon in your system tray (bottom right)")
    print("Requires: bash (Git Bash or WSL) and tmux")
    app = ClaudeUsageTray()
    app.run()


if __name__ == "__main__":
    main()
