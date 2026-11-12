# niri / DMS Battery view

Adds K2 HE and M3 Lite readings inside DMS's existing Battery view, shared by
the bar Battery popout and Control Center battery details. No dedicated bar
widget or icon is added. Rows include percentage, charging state, connection,
keyboard voltage, and a last-known indicator. Unavailable readings show N/A;
levels below 20% use the theme error color. The existing bar battery icon also
turns red if either device is below 20%; 20% itself does not trigger the warning.

Requires the existing `keychron-battery.service` and
`keychron-keyboard-battery.service`, with device permissions and keyboard
firmware as described in INSTALL.md and FLASHING.md. The view reads their
atomic runtime JSON files asynchronously; it never queries HID hardware.
Snapshots expire three minutes after the last observation or service update.

DMS does not expose a plugin slot in its native Battery view, so this integration
creates a local copy of its UI with one additional component, then selects it
using a user systemd service drop-in (`DMS_SHELL_DIR`). The installed DMS package
is unchanged. After upgrading DMS, rerun the installer against the new embedded
UI to refresh this local copy. Do not run the GNOME installer just for DMS.

For the already configured niri/DMS system:

```sh
python3 install_dms.py --shell-source /run/user/$UID/dms-shell/<current-ui-hash>
```

The source must be the current DMS UI directory containing `shell.qml`.
The installer backs up settings, removes any previous dedicated Keychron bar
widget, installs the native view in `~/.config/dms/keychron-shell`, and restarts
DMS. Use `--no-restart` to stage files. Repeated runs do not duplicate the panel.

To remove the native view override, remove
`~/.config/systemd/user/dms.service.d/keychron.conf`, run
`systemctl --user daemon-reload`, then `systemctl --user restart dms.service`.
The optional `~/.config/dms/keychron-shell` copy can then be deleted.
Battery services may remain running for other integrations.

Validation: `node tests/test_dms.cjs` checks fresh, cached, expired, malformed,
missing, charging, full, and zero-percent snapshots. The view samples wall time
on every new snapshot, preventing fresh data being rejected just because it
arrived after the last five-second timer tick. Transient file reload failures
retain the previous snapshot until normal expiry.
