#!/usr/bin/env python3
"""
Shared usage fetcher - handles fetching, parsing, caching, and error tracking.
Platform-specific UIs should use this class instead of implementing their own logic.
"""

import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Callable, Any

SCRIPT_DIR = Path(__file__).parent


class UsageFetcher:
    """Fetches Claude usage data with caching and error handling."""

    def __init__(self, on_update: Callable[[Dict[str, Any]], None] = None):
        """
        Initialize the fetcher.

        Args:
            on_update: Callback called on main thread when data changes.
                       Receives a dict with: data, is_stale, error, status, fetch_count
        """
        self.on_update = on_update

        # State
        self.last_good_data: Optional[Dict[str, str]] = None
        self.last_successful_fetch: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.fetch_count = 0
        self.is_fetching = False
        self.is_stale = False

        # For main thread scheduling (set by platform-specific code)
        self._schedule_on_main_thread: Optional[Callable] = None

    def set_main_thread_scheduler(self, scheduler: Callable):
        """Set the function to schedule callbacks on main thread."""
        self._schedule_on_main_thread = scheduler

    def _notify_update(self, status: str, error: Optional[str] = None):
        """Notify listeners of state change."""
        if not self.on_update:
            return

        state = {
            'data': self.last_good_data,
            'is_stale': self.is_stale,
            'error': error or self.last_error,
            'status': status,
            'fetch_count': self.fetch_count,
            'last_successful_fetch': self.last_successful_fetch,
            'is_fetching': self.is_fetching,
        }

        if self._schedule_on_main_thread:
            self._schedule_on_main_thread(self.on_update, state)
        else:
            self.on_update(state)

    def fetch_async(self):
        """Start a fetch in background thread."""
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _do_fetch(self):
        """Perform the fetch (runs in background thread)."""
        self.fetch_count += 1
        self.is_fetching = True
        fetch_num = self.fetch_count
        start_time = datetime.now()

        self._notify_update(f"Fetching #{fetch_num} (started {start_time.strftime('%H:%M:%S')})...")

        try:
            script_path = SCRIPT_DIR / "fetch_usage.sh"

            result = subprocess.run(
                ["bash", str(script_path)],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=str(SCRIPT_DIR)
            )

            self.is_fetching = False

            if result.returncode != 0:
                stderr_preview = result.stderr[:100].replace('\n', ' ') if result.stderr else "no stderr"
                self.last_error = f"Script exit {result.returncode}: {stderr_preview}"
                self.is_stale = True
                self._notify_update(f"Error @ {datetime.now().strftime('%H:%M:%S')}", self.last_error)
                return

            # Parse the output
            self._parse_output(result.stdout, fetch_num)

        except subprocess.TimeoutExpired:
            self.is_fetching = False
            self.last_error = "Timeout after 90s"
            self.is_stale = True
            self._notify_update(f"Timeout @ {datetime.now().strftime('%H:%M:%S')}", self.last_error)

        except Exception as e:
            self.is_fetching = False
            self.last_error = f"{type(e).__name__}: {str(e)}"
            self.is_stale = True
            self._notify_update(f"Error @ {datetime.now().strftime('%H:%M:%S')}", self.last_error)

    def _parse_output(self, output: str, fetch_num: int):
        """Parse key=value output from fetch_usage.sh."""
        try:
            data = {}
            for line in output.strip().split('\n'):
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    data[key.strip()] = value.strip()

            session_remaining = data.get('SESSION_REMAINING', '??')
            weekly_remaining = data.get('WEEKLY_REMAINING', '??')

            has_valid_data = session_remaining != '??' and weekly_remaining != '??'

            if has_valid_data:
                self.last_good_data = data.copy()
                self.last_successful_fetch = datetime.now()
                self.is_stale = False
                self.last_error = None
                self._notify_update(f"OK (fetch #{fetch_num}) @ {datetime.now().strftime('%H:%M:%S')}")
            else:
                self.last_error = f"Got ?? values (parsed {len(data)} keys)"
                self.is_stale = True
                self._notify_update(f"Invalid data @ {datetime.now().strftime('%H:%M:%S')}", self.last_error)

        except Exception as e:
            self.last_error = f"Parse error: {str(e)}"
            self.is_stale = True
            self._notify_update(f"Parse error @ {datetime.now().strftime('%H:%M:%S')}", self.last_error)


# Convenience function to extract common display values
def get_display_values(data: Optional[Dict[str, str]]) -> Dict[str, Any]:
    """Extract display-ready values from fetched data."""
    if not data:
        return {
            'session_remaining': '--',
            'weekly_remaining': '--',
            'time_remaining_str': None,
            'confidence': None,
            'session_resets': None,
            'weekly_resets': None,
            'exhausts_before_reset': False,
            'account_email': None,
            'plan_type': None,
            'extra_pct': None,
        }

    return {
        'session_remaining': data.get('SESSION_REMAINING', '??'),
        'weekly_remaining': data.get('WEEKLY_REMAINING', '??'),
        'time_remaining_str': data.get('TIME_REMAINING_STR'),
        'confidence': data.get('CONFIDENCE'),
        'session_resets': data.get('SESSION_RESETS'),
        'weekly_resets': data.get('WEEKLY_RESETS'),
        'exhausts_before_reset': data.get('EXHAUSTS_BEFORE_RESET') == 'true',
        'account_email': data.get('ACCOUNT_EMAIL'),
        'plan_type': data.get('PLAN_TYPE'),
        'extra_pct': data.get('EXTRA_USED'),
    }
