#!/usr/bin/env python3
"""
Claude Usage Menu Bar - macOS status bar utility
Shows Claude Code usage with AI-powered predictions.
"""

import sys
from pathlib import Path

# Hide dock icon before importing rumps
try:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
except ImportError:
    pass

import rumps

# Add parent directory to path for shared modules
SCRIPT_DIR = Path(__file__).parent.parent / "claude-usage@local"
sys.path.insert(0, str(SCRIPT_DIR))

from usage_fetcher import UsageFetcher, get_display_values

REFRESH_INTERVAL_SECONDS = 300  # 5 minutes


class ClaudeUsageApp(rumps.App):
    def __init__(self):
        super().__init__("Claude Usage", icon=None, title="🤖 --", quit_button=None)

        # Menu items
        self.account_item = rumps.MenuItem("Account: --")
        self.session_item = rumps.MenuItem("Session: Loading...")
        self.time_remaining_item = rumps.MenuItem("Depletes: --")
        self.session_resets_item = rumps.MenuItem("Resets: --")
        self.weekly_item = rumps.MenuItem("Weekly: Loading...")
        self.weekly_resets_item = rumps.MenuItem("Resets: --")
        self.last_updated_item = rumps.MenuItem("Last updated: Never")
        self.status_item = rumps.MenuItem("Status: Starting...")
        self.error_item = rumps.MenuItem("Last error: None")

        self.menu = [
            self.account_item,
            None,
            self.session_item,
            self.time_remaining_item,
            self.session_resets_item,
            None,
            self.weekly_item,
            self.weekly_resets_item,
            None,
            self.last_updated_item,
            self.status_item,
            self.error_item,
            None,
            rumps.MenuItem("Refresh Now", callback=self.refresh_clicked),
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

        # Set up shared fetcher
        self.fetcher = UsageFetcher(on_update=self._on_fetcher_update)
        self.fetcher.set_main_thread_scheduler(self._run_on_main_thread)

        # Start refresh timer and initial fetch
        self.timer = rumps.Timer(self.refresh_timer, REFRESH_INTERVAL_SECONDS)
        self.timer.start()
        self.fetcher.fetch_async()

    def _run_on_main_thread(self, func, *args, **kwargs):
        """Schedule function on main thread for UI updates."""
        try:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(func, *args, **kwargs)
        except ImportError:
            func(*args, **kwargs)

    def refresh_clicked(self, _):
        self.fetcher.fetch_async()

    def refresh_timer(self, _):
        self.fetcher.fetch_async()

    def _on_fetcher_update(self, state):
        """Called when fetcher state changes (on main thread)."""
        data = state['data']
        is_stale = state['is_stale']
        error = state['error']
        status = state['status']
        is_fetching = state['is_fetching']
        last_successful = state['last_successful_fetch']

        # Update status
        if is_fetching:
            self.title = "🤖 ⟳"
        self.status_item.title = f"Status: {status}"

        # Update error display
        if error:
            self.error_item.title = f"Last error: {error}"
        else:
            self.error_item.title = "Last error: None"

        # Update data display
        if data:
            self._update_ui_from_data(data, is_stale)
        elif not is_fetching:
            # No data and not fetching - show waiting state
            robot = "😴"
            self.title = f"{robot} --"
            self.session_item.title = "Session: Waiting for data..."
            self.weekly_item.title = "Weekly: Waiting for data..."

        # Update last updated time
        if last_successful:
            suffix = " (stale)" if is_stale else ""
            self.last_updated_item.title = f"Last updated: {last_successful.strftime('%H:%M:%S')}{suffix}"

    def _update_ui_from_data(self, data, is_stale):
        """Update UI from fetched data."""
        v = get_display_values(data)

        robot = "😴" if is_stale else "🤖"
        warning = "⚠️ " if v['exhausts_before_reset'] else ""

        # Title
        if v['time_remaining_str']:
            self.title = f"{warning}{robot} {v['time_remaining_str']} ({v['session_remaining']}%)"
        else:
            self.title = f"{robot} W:{v['weekly_remaining']}% S:{v['session_remaining']}%"

        # Account
        if v['account_email']:
            account_text = f"Account: {v['account_email']}"
            if v['plan_type']:
                account_text += f" ({v['plan_type']})"
            self.account_item.title = account_text
        else:
            self.account_item.title = "Account: --"

        # Session
        self.session_item.title = f"Session remaining: {v['session_remaining']}%"

        if v['time_remaining_str']:
            time_text = f"Depletes in ~{v['time_remaining_str']}"
            if v['confidence']:
                try:
                    conf = round(float(v['confidence']) * 100)
                    time_text += f" ({conf}% conf)"
                except:
                    pass
            if v['exhausts_before_reset']:
                time_text += " ⚠️ before reset!"
            self.time_remaining_item.title = time_text
        else:
            self.time_remaining_item.title = "Depletes: --"

        if v['session_resets']:
            self.session_resets_item.title = f"Resets at {v['session_resets']}"
        else:
            self.session_resets_item.title = "Resets: --"

        # Weekly
        weekly_text = f"Weekly remaining: {v['weekly_remaining']}%"
        if v['extra_pct']:
            weekly_text += f" (Extra: {v['extra_pct']}% used)"
        self.weekly_item.title = weekly_text

        if v['weekly_resets']:
            self.weekly_resets_item.title = f"Resets {v['weekly_resets']}"
        else:
            self.weekly_resets_item.title = "Resets: --"


if __name__ == "__main__":
    ClaudeUsageApp().run()
