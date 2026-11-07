# Installation guide

## 1. Check prerequisites

Install Vitals using your distribution or
[GNOME Extensions](https://extensions.gnome.org/extension/1460/vitals/).
Use GNOME with a systemd user session and a USB-connected Link-KM receiver or
wired M3 Lite. The current implementation targets Vitals 86's `_queryBattery`
interface; the installer rejects a missing hook.

On Fedora, the Python and test runtime dependencies are:

```sh
sudo dnf install python3 python3-gobject gjs git
```

On Debian/Ubuntu:

```sh
sudo apt install python3 python3-gi gjs git
```

Your desktop installation must also provide `systemctl`, `udevadm`, and
`gnome-extensions`. Check the Python bindings:

```sh
/usr/bin/python3 -c 'from gi.repository import Gio; print("Gio available")'
```

## 2. Install as your desktop user

```sh
git clone https://github.com/nwadams/keychron-vitals.git
cd keychron-vitals
/usr/bin/python3 install_vitals.py
```

Do not run the entire installer with sudo. It performs these changes:

- Installs a local Vitals copy in
  `~/.local/share/gnome-shell/extensions/Vitals@CoreCoding.com` with two new
  Battery rows. Existing local Vitals files are backed up under
  `~/.local/state/keychron-battery/extension-backup`.
- Installs `~/.config/systemd/user/keychron-battery.service` and enables it for
  the graphical session. It polls every 30 seconds without root.
- Installs `/etc/udev/rules.d/70-keychron-m3-battery.rules` using sudo and
  reloads/retriggers udev so the active local user gets HID access. The rule
  targets Link-KM mouse interface 01 and the wired M3 Lite USB ID.
- Enables Vitals Battery and adds `_battery_keychron_m3_lite_` to its pinned
  sensors. Other pinned sensors are retained. It adds and selects **Keychron M3
  Lite** in Battery Preferences → Display Battery, which makes the collapsed
  Battery summary show the mouse percentage.

The receiver vendor collection shares a HID interface with additional reports;
as with other HID utilities, granting device access grants access to that
interface. The service uses only the mouse status and connection queries.

**Log out and back in** after installation. GNOME Shell must load the local
extension copy; toggling the already-loaded extension may retain old modules.
No reboot is required. If HID access still fails, reconnect the receiver.

In Vitals, open **Battery**. You should see **Keychron M3 Lite** and
**Keychron M3 Lite State**. The percentage is automatically pinned to the top
bar; click its Vitals row to change that preference. Battery Preferences →
Display Battery includes **Keychron M3 Lite**; selecting it uses the mouse
percentage for the Battery summary. Built-in battery choices retain their
existing behavior.

For file preparation without sudo, D-Bus, or service activation:

```sh
/usr/bin/python3 install_vitals.py --stage
```

Then run the installer without flags on the host desktop to activate it.

## 3. Verify a live reading

Wake the mouse and close Keychron Launcher before checking:

```sh
systemctl --user status keychron-battery.service
cat "$XDG_RUNTIME_DIR/keychron-battery/status.json"
/usr/bin/python3 battery_service.py --once
```

The one-shot command prints JSON and exits with status 1 when no validated
reading is available. It does not change the service's snapshot.

For diagnostics:

```sh
journalctl --user -u keychron-battery.service -n 30 --no-pager
gnome-extensions info Vitals@CoreCoding.com
```

The snapshot includes `reading.battery_percent`, `reading.charging`,
`reading.connection`, `observed_at`, `updated_at`, and query errors. It does not
include raw input packets. A missing response can be normal for a sleeping mouse.

## Troubleshooting

**N/A:** Wake the mouse, wait 30 seconds, and check the service journal. The app
requires a confirmed mouse connection before accepting a receiver reading.
Bluetooth is unsupported.

**Permission denied:** Run installation from your active local desktop session,
then reconnect the receiver. Do not make every HID device world-writable.
Check the target with `udevadm info -q property -n /dev/hidrawN`; for Link-KM,
`ID_USB_INTERFACE_NUM` must be `01` on the mouse vendor endpoint. Other firmware
or receiver layouts may need a revised narrowly scoped rule.

**JSON updates but Vitals has no mouse row:** Log out/in and confirm GNOME loads
the extension from your home directory with `gnome-extensions info`. Enable
Battery in Vitals preferences. The integration is inside Vitals, so it must be
enabled for the row to appear.

**Battery summary says “No Data” while the mouse row has a percentage:** Update
and rerun the installer, then log out/in. In Battery Preferences → Display
Battery select **Keychron M3 Lite**. BAT0/BAT1/BAT2 refer to built-in batteries,
not the mouse. An unavailable or expired mouse reading displays **N/A**.

**Systemd or HID devices unavailable:** Run the installer and service on your
host, outside a container or restricted coding session.

**Installer fails midway:** User files and backup metadata remain in place.
Resolve the reported error and rerun the same command; staging is idempotent.

## Updating

For an app update, keep the checkout in place:

```sh
git pull --ff-only
/usr/bin/python3 install_vitals.py
systemctl --user restart keychron-battery.service
```

Log out and back in if JavaScript changed. The service uses an absolute checkout
path, so moving or deleting it requires reinstalling from the new location.

The local Vitals copy masks system package updates. To move to a newer Vitals
version, uninstall this integration, update Vitals normally, then reinstall and
verify compatibility. Uninstallation restores the original local copy, if any.

## Uninstall

```sh
/usr/bin/python3 install_vitals.py --uninstall
```

The uninstaller stops/disables the service, removes its unit and custom udev
rule, restores the previous local Vitals copy (or removes the local override),
and restores the previous Battery visibility and display battery selection. It removes its own pinned sensor
if installation added it. Log out and back in afterward.

If you only staged files and never activated, use the same uninstaller. When
the service was never loaded, a harmless “unit does not exist” message may
appear.
