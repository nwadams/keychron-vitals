# Keychron Vitals

Show your **Keychron M3 Lite mouse battery** in the **Battery** section of the
Vitals GNOME Shell extension and pin its percentage to the system top bar.

The app polls the mouse every 30 seconds in a systemd user service. Vitals reads
a small local JSON snapshot asynchronously, so USB queries never block GNOME
Shell. It reports percentage, charging state, and USB or 2.4 GHz connection.

## Install

Requires Linux with GNOME, [Vitals](https://github.com/corecoding/Vitals), Python 3,
Python GObject bindings (`gi`), systemd, udev, and `gnome-extensions`.
The integration has been tested against the installed Vitals 86 source and
GNOME 51 environment; live service activation and panel rendering still require
verification on the host desktop.

```sh
git clone https://github.com/nwadams/keychron-vitals.git
cd keychron-vitals
/usr/bin/python3 install_vitals.py
```

Run the installer **as your desktop user**, in a normal host terminal. It invokes
sudo only to install/reload a device access rule. Log out and back in afterward
to load the local Vitals extension. The installer enables Battery and pins
**Keychron M3 Lite** while preserving your other pinned sensors. It also selects
**Keychron M3 Lite** under Battery Preferences → Display Battery, so the collapsed
Battery summary shows the mouse percentage.

See **[INSTALL.md](INSTALL.md)** for dependencies, verification, troubleshooting,
updates, and removal. Keep the checkout at its installed path: the service runs
the Python files from that directory.

## Supported hardware

| Device | USB ID | Transport |
| --- | --- | --- |
| M3 Lite through Keychron Link-KM | `3434:d026` | 2.4 GHz receiver |
| Wired M3 Lite | `3434:d04e` | USB |

This app uses a protocol previously verified on this mouse and receiver, with
the battery layout checked against the official Keychron Launcher JavaScript.
Bluetooth and other Keychron models are not implemented.

Wired readings take priority. Receiver readings require a confirmed connected
M3 Lite slot, avoiding old receiver values while the mouse is on USB. If a poll
fails, the last successful reading can remain for up to three minutes, marked
“last known” in the State row. Older readings, a stopped service, and malformed
snapshots display **N/A**. Wake the mouse and close Keychron Launcher if queries
time out.

## How it works

1. `mouse_protocol.py` discovers the vendor HID collection and sends read-only
   status requests (`B3/03` receiver state; `B3/06` battery).
2. `battery_service.py` writes `$XDG_RUNTIME_DIR/keychron-battery/status.json`
   atomically with user-only permissions.
3. `vitals/keychronBattery.js` adds percentage and state rows to Vitals Battery
   and supplies its summary when Keychron is selected.
4. `install_vitals.py` makes a local copy of your installed Vitals extension,
   adds the reader, and configures the service and pinned sensor.

The system Vitals extension stays on disk. Any pre-existing local Vitals copy is
backed up before modification. This is a local extension customization: future
Vitals updates may replace it or be hidden by it. Review the update instructions.

## Protocol

The 64-byte mouse response starts `B4 06`. Byte 20 includes both fields:

```python
percentage = packet[20] & 0x7f
charging = bool(packet[20] & 0x80)
```

Percentages above 100 and malformed packets are rejected. For example, `0x08`
is 8% discharging and `0x8B` is 11% charging. No configuration, pairing, or
firmware commands are sent. Source metadata is in
[protocol-evidence.json](protocol-evidence.json). The referenced public vendor
bundle is not redistributed.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
```

Tests cover battery/charge decoding, packet boundaries, wired priority,
receiver connection checks, permission failures, cache expiry, atomic output,
idempotent Vitals patching, and the real asynchronous GJS reader. GJS checks are
skipped when `gjs` is absent; the installed-extension check is skipped if Vitals
is absent. Tests do not need mouse hardware or root. The included CI runs Python
and GJS checks.

The existing hardware captures used to establish the protocol predate this
app. The automated tests simulate device replies; they do not claim a live
end-to-end hardware or desktop test of this integration.

MIT licensed. Vitals retains its own license; the installer copies the user's
installed extension locally rather than distributing it in this repository.
