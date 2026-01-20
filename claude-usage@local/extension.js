import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

const REFRESH_INTERVAL_SECONDS = 300; // 5 minutes

export default class ClaudeUsageExtension extends Extension {
    _indicator = null;
    _timeout = null;

    // Cached data state
    _lastGoodData = null;
    _lastSuccessfulFetch = null;
    _isStale = false;
    _lastError = null;
    _fetchCount = 0;
    _status = 'Starting...';

    enable() {
        this._indicator = new PanelMenu.Button(0.0, 'Claude Usage', false);

        // Create the panel label
        this._panelLabel = new St.Label({
            text: '🤖 --',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'panel-button-text'
        });
        this._indicator.add_child(this._panelLabel);

        // Create menu items
        this._accountMenuItem = new PopupMenu.PopupMenuItem('Account: --');
        this._accountMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._accountMenuItem);

        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._sessionMenuItem = new PopupMenu.PopupMenuItem('Session: Loading...');
        this._sessionMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._sessionMenuItem);

        this._timeRemainingMenuItem = new PopupMenu.PopupMenuItem('Time remaining: --');
        this._timeRemainingMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._timeRemainingMenuItem);

        this._sessionResetsMenuItem = new PopupMenu.PopupMenuItem('Resets: --');
        this._sessionResetsMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._sessionResetsMenuItem);

        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._weeklyMenuItem = new PopupMenu.PopupMenuItem('Weekly: Loading...');
        this._weeklyMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._weeklyMenuItem);

        this._weeklyResetsMenuItem = new PopupMenu.PopupMenuItem('Resets: --');
        this._weeklyResetsMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._weeklyResetsMenuItem);

        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._lastUpdatedMenuItem = new PopupMenu.PopupMenuItem('Last updated: Never');
        this._lastUpdatedMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._lastUpdatedMenuItem);

        this._statusMenuItem = new PopupMenu.PopupMenuItem('Status: Starting...');
        this._statusMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._statusMenuItem);

        this._errorMenuItem = new PopupMenu.PopupMenuItem('Last error: None');
        this._errorMenuItem.sensitive = false;
        this._indicator.menu.addMenuItem(this._errorMenuItem);

        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Refresh button
        const refreshItem = new PopupMenu.PopupMenuItem('Refresh Now');
        refreshItem.connect('activate', () => {
            this._fetchUsage();
        });
        this._indicator.menu.addMenuItem(refreshItem);

        Main.panel.addToStatusArea(this.uuid, this._indicator);

        // Initial fetch
        this._fetchUsage();

        // Set up periodic refresh
        this._timeout = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            REFRESH_INTERVAL_SECONDS,
            () => {
                this._fetchUsage();
                return GLib.SOURCE_CONTINUE;
            }
        );
    }

    disable() {
        if (this._timeout) {
            GLib.Source.remove(this._timeout);
            this._timeout = null;
        }

        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }

    _fetchUsage() {
        this._fetchCount++;
        const fetchNum = this._fetchCount;
        const startTime = new Date().toLocaleTimeString();

        // Update UI to show loading
        this._panelLabel.set_text('🤖 ⟳');
        this._status = `Fetching #${fetchNum} (started ${startTime})...`;
        this._statusMenuItem.label.set_text(`Status: ${this._status}`);

        // Get the extension's directory for the helper script
        const extensionDir = this.path;
        const scriptPath = GLib.build_filenamev([extensionDir, 'fetch_usage.sh']);

        try {
            const proc = Gio.Subprocess.new(
                ['bash', scriptPath],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );

            proc.communicate_utf8_async(null, null, (proc, res) => {
                try {
                    const [, stdout, stderr] = proc.communicate_utf8_finish(res);
                    const exitStatus = proc.get_exit_status();

                    if (exitStatus !== 0) {
                        this._setError(`Script exit ${exitStatus}: ${stderr.slice(0, 50)}`);
                        return;
                    }

                    this._parseUsage(stdout, fetchNum);
                } catch (e) {
                    log(`Claude Usage Extension: Error reading output: ${e.message}`);
                    this._setError(`Read error: ${e.message.slice(0, 30)}`);
                }
            });
        } catch (e) {
            log(`Claude Usage Extension: Error spawning process: ${e.message}`);
            this._setError(`Spawn error: ${e.message.slice(0, 30)}`);
        }
    }

    _parseUsage(output, fetchNum) {
        try {
            // Parse key=value format from fetch_usage.sh
            const lines = output.split('\n');
            const data = {};

            for (const line of lines) {
                const match = line.match(/^([A-Z_]+)=(.+)$/);
                if (match) {
                    data[match[1]] = match[2];
                }
            }

            const sessionRemaining = data['SESSION_REMAINING'];
            const weeklyRemaining = data['WEEKLY_REMAINING'];

            // Check if we got valid data
            const hasValidData = sessionRemaining && sessionRemaining !== '??' &&
                                 weeklyRemaining && weeklyRemaining !== '??';

            if (hasValidData) {
                // Cache the good data
                this._lastGoodData = data;
                this._lastSuccessfulFetch = new Date();
                this._isStale = false;
                this._lastError = null;
                this._status = `OK (fetch #${fetchNum}) @ ${new Date().toLocaleTimeString()}`;
                this._statusMenuItem.label.set_text(`Status: ${this._status}`);
                this._errorMenuItem.label.set_text('Last error: None');
                this._updateUIFromData(data);
            } else {
                this._setError(`Got ?? values (parsed ${Object.keys(data).length} keys)`);
            }

        } catch (e) {
            log(`Claude Usage Extension: Error parsing usage: ${e.message}`);
            this._setError(`Parse error: ${e.message.slice(0, 30)}`);
        }
    }

    _updateUIFromData(data) {
        const accountEmail = data['ACCOUNT_EMAIL'];
        const planType = data['PLAN_TYPE'];
        const sessionRemaining = data['SESSION_REMAINING'] || '??';
        const weeklyRemaining = data['WEEKLY_REMAINING'] || '??';
        const extraUsed = data['EXTRA_USED'];
        const timeRemainingStr = data['TIME_REMAINING_STR'];
        const confidence = data['CONFIDENCE'];
        const sessionResets = data['SESSION_RESETS'];
        const weeklyResets = data['WEEKLY_RESETS'];
        const exhaustsBeforeReset = data['EXHAUSTS_BEFORE_RESET'] === 'true';

        // Determine robot emoji
        const robot = this._isStale ? '😴' : '🤖';
        const warning = exhaustsBeforeReset ? '⚠️ ' : '';

        // Update panel label
        if (timeRemainingStr) {
            this._panelLabel.set_text(`${warning}${robot} ${timeRemainingStr} (${sessionRemaining}%)`);
        } else {
            this._panelLabel.set_text(`${robot} W:${weeklyRemaining}% S:${sessionRemaining}%`);
        }

        // Update account info
        if (accountEmail) {
            let accountText = `Account: ${accountEmail}`;
            if (planType) {
                accountText += ` (${planType})`;
            }
            this._accountMenuItem.label.set_text(accountText);
        } else {
            this._accountMenuItem.label.set_text('Account: --');
        }

        // Session info
        const staleSuffix = this._isStale ? ' (stale)' : '';
        this._sessionMenuItem.label.set_text(`Session remaining: ${sessionRemaining}%${staleSuffix}`);

        // Time remaining
        if (timeRemainingStr) {
            let timeText = `Depletes in ~${timeRemainingStr}`;
            if (confidence) {
                const conf = Math.round(parseFloat(confidence) * 100);
                timeText += ` (${conf}% conf)`;
            }
            if (exhaustsBeforeReset) {
                timeText += ' ⚠️ before reset!';
            }
            this._timeRemainingMenuItem.label.set_text(timeText);
        } else {
            this._timeRemainingMenuItem.label.set_text('Depletes: --');
        }

        // Session reset time
        if (sessionResets) {
            this._sessionResetsMenuItem.label.set_text(`Resets at ${sessionResets}`);
        } else {
            this._sessionResetsMenuItem.label.set_text('Resets: --');
        }

        // Weekly info
        let weeklyText = `Weekly remaining: ${weeklyRemaining}%`;
        if (extraUsed) {
            weeklyText += ` (Extra: ${extraUsed}% used)`;
        }
        this._weeklyMenuItem.label.set_text(weeklyText);

        // Weekly reset time
        if (weeklyResets) {
            this._weeklyResetsMenuItem.label.set_text(`Resets ${weeklyResets}`);
        } else {
            this._weeklyResetsMenuItem.label.set_text('Resets: --');
        }

        // Last updated
        if (this._lastSuccessfulFetch) {
            const suffix = this._isStale ? ' (stale)' : '';
            this._lastUpdatedMenuItem.label.set_text(`Last updated: ${this._lastSuccessfulFetch.toLocaleTimeString()}${suffix}`);
        }
    }

    _setError(msg) {
        this._lastError = msg;
        this._isStale = true;
        this._status = `Error @ ${new Date().toLocaleTimeString()}`;

        this._statusMenuItem.label.set_text(`Status: ${this._status}`);
        this._errorMenuItem.label.set_text(`Last error: ${msg}`);

        // Use cached data if available, otherwise show error state
        if (this._lastGoodData) {
            this._updateUIFromData(this._lastGoodData);
        } else {
            this._panelLabel.set_text('😴 --');
            this._sessionMenuItem.label.set_text('Session: Waiting for data...');
            this._weeklyMenuItem.label.set_text('Weekly: Waiting for data...');
        }
    }
}
