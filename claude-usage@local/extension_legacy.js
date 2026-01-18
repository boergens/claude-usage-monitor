/* extension_legacy.js - For GNOME 42-44 (non-ESM)
 *
 * To use this version:
 * 1. Rename extension.js to extension_modern.js
 * 2. Rename this file to extension.js
 * 3. Update metadata.json to only include ["42", "43", "44"]
 */

const { GLib, Gio, St, Clutter } = imports.gi;
const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const ExtensionUtils = imports.misc.extensionUtils;

const REFRESH_INTERVAL_SECONDS = 300;

let indicator = null;
let timeout = null;
let panelLabel = null;
let sessionMenuItem = null;
let weeklyMenuItem = null;
let lastUpdatedMenuItem = null;

function init() {
    // Nothing to initialize
}

function enable() {
    indicator = new PanelMenu.Button(0.0, 'Claude Usage', false);

    panelLabel = new St.Label({
        text: '🤖 --',
        y_align: Clutter.ActorAlign.CENTER
    });
    indicator.add_child(panelLabel);

    sessionMenuItem = new PopupMenu.PopupMenuItem('Session: Loading...');
    sessionMenuItem.sensitive = false;
    indicator.menu.addMenuItem(sessionMenuItem);

    weeklyMenuItem = new PopupMenu.PopupMenuItem('Weekly: Loading...');
    weeklyMenuItem.sensitive = false;
    indicator.menu.addMenuItem(weeklyMenuItem);

    indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

    lastUpdatedMenuItem = new PopupMenu.PopupMenuItem('Last updated: Never');
    lastUpdatedMenuItem.sensitive = false;
    indicator.menu.addMenuItem(lastUpdatedMenuItem);

    indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

    const refreshItem = new PopupMenu.PopupMenuItem('Refresh Now');
    refreshItem.connect('activate', () => {
        fetchUsage();
    });
    indicator.menu.addMenuItem(refreshItem);

    Main.panel.addToStatusArea('claude-usage', indicator);

    fetchUsage();

    timeout = GLib.timeout_add_seconds(
        GLib.PRIORITY_DEFAULT,
        REFRESH_INTERVAL_SECONDS,
        () => {
            fetchUsage();
            return GLib.SOURCE_CONTINUE;
        }
    );
}

function disable() {
    if (timeout) {
        GLib.Source.remove(timeout);
        timeout = null;
    }

    if (indicator) {
        indicator.destroy();
        indicator = null;
    }
}

function fetchUsage() {
    panelLabel.set_text('🤖 ⟳');

    const extensionDir = ExtensionUtils.getCurrentExtension().path;
    const scriptPath = GLib.build_filenamev([extensionDir, 'fetch_usage.sh']);

    try {
        const proc = Gio.Subprocess.new(
            ['bash', scriptPath],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
        );

        proc.communicate_utf8_async(null, null, (proc, res) => {
            try {
                const [, stdout, stderr] = proc.communicate_utf8_finish(res);
                parseUsage(stdout);
            } catch (e) {
                log(`Claude Usage Extension: Error reading output: ${e.message}`);
                setError('Error');
            }
        });
    } catch (e) {
        log(`Claude Usage Extension: Error spawning process: ${e.message}`);
        setError('Error');
    }
}

function parseUsage(output) {
    try {
        const lines = output.split('\n');
        let sessionPercent = null;
        let weeklyPercent = null;

        for (const line of lines) {
            const lowerLine = line.toLowerCase();

            if (lowerLine.includes('session') || lowerLine.includes('current')) {
                const match = line.match(/(\d+(?:\.\d+)?)\s*%/);
                if (match) {
                    sessionPercent = parseFloat(match[1]);
                }
            }

            if (lowerLine.includes('week')) {
                const match = line.match(/(\d+(?:\.\d+)?)\s*%/);
                if (match) {
                    weeklyPercent = parseFloat(match[1]);
                }
            }

            if (sessionPercent === null && (lowerLine.includes('session') || lowerLine.includes('current'))) {
                const fractionMatch = line.match(/(\d+)\s*\/\s*(\d+)/);
                if (fractionMatch) {
                    sessionPercent = (parseInt(fractionMatch[1]) / parseInt(fractionMatch[2])) * 100;
                }
            }

            if (weeklyPercent === null && lowerLine.includes('week')) {
                const fractionMatch = line.match(/(\d+)\s*\/\s*(\d+)/);
                if (fractionMatch) {
                    weeklyPercent = (parseInt(fractionMatch[1]) / parseInt(fractionMatch[2])) * 100;
                }
            }
        }

        if (sessionPercent === null && weeklyPercent === null) {
            const allPercents = output.match(/(\d+(?:\.\d+)?)\s*%/g);
            if (allPercents && allPercents.length >= 2) {
                sessionPercent = parseFloat(allPercents[0]);
                weeklyPercent = parseFloat(allPercents[1]);
            } else if (allPercents && allPercents.length === 1) {
                weeklyPercent = parseFloat(allPercents[0]);
            }
        }

        const sessionRemaining = sessionPercent !== null ? (100 - sessionPercent).toFixed(1) : '??';
        const weeklyRemaining = weeklyPercent !== null ? (100 - weeklyPercent).toFixed(1) : '??';

        panelLabel.set_text(`🤖 ${weeklyRemaining}%`);
        sessionMenuItem.label.set_text(`Session remaining: ${sessionRemaining}%`);
        weeklyMenuItem.label.set_text(`Weekly remaining: ${weeklyRemaining}%`);

        const now = new Date();
        lastUpdatedMenuItem.label.set_text(`Last updated: ${now.toLocaleTimeString()}`);

    } catch (e) {
        log(`Claude Usage Extension: Error parsing usage: ${e.message}`);
        setError('Parse error');
    }
}

function setError(msg) {
    panelLabel.set_text(`🤖 ${msg}`);
    sessionMenuItem.label.set_text(`Session: ${msg}`);
    weeklyMenuItem.label.set_text(`Weekly: ${msg}`);
}
