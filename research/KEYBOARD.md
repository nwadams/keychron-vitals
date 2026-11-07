# K2 HE battery telemetry investigation

For step-by-step build, flashing, verification and rollback commands, see
[the flashing and rollback guide](../FLASHING.md).

The user's keyboard is a **K2 HE ANSI**, USB `3434:0e20`, paired with a
Link-KM `3434:d026` receiver. Stock keyboard firmware observed locally:
`v1.1.0 2024-10-31-09:00:44`; receiver: `0.1.1 Feb 18 2025 14:54:01`.

## Findings

The stock wired keyboard responds to A0/A1/A2 identity getters but returns
`FF` (unsupported) for A4. A 12-second vendor-only receiver capture produced
valid keyboard/mouse slot identities, no errors, and no keyboard battery
reports. This does not prove that all hidden stock commands lack telemetry.
No stock keyboard percentage was recovered.

[Keyboard Companion](https://github.com/OutersGIT/keyboard-companion) identifies
a workable custom protocol. Its [K10 HE firmware](https://github.com/OutersGIT/k10he-battery-firmware)
adds a getter and unsolicited reports. Host-to-keyboard raw-HID requests may
not be bridged by the dongle; keyboard-to-host push avoids that problem.
Its ready-made K10 HE/Q1 HE binaries are not K2 HE firmware.

The official [K2 HE source](https://github.com/Keychron/qmk_firmware/tree/57e682caa0a821e6de1b589e6f983f266151ab02/keyboards/keychron/k2_he)
uses the same shared battery and wireless functions. The experimental patch
in `firmware/k2-he-battery-telemetry.patch` enables telemetry only for K2 HE:

- A4 getter over USB and two-second pushes over connected 2.4 GHz.
- Existing battery percentage/voltage calculation and charging pin.
- Cable-mode voltage polling to avoid an old wireless voltage snapshot.
- Battery capability bit 10; model id 0 (unspecified), preserving upstream ids.

Raw 32-byte report: `A4 percent mV_lo mV_hi charge transport model`, then zeros.
Charge: 0 discharging, 1 charging, 2 full. Transport: 1 USB, 2 Bluetooth,
4 receiver. This is a custom protocol, not a newly discovered stock getter.
The voltage-derived percentage is the keyboard's estimate, not a calibrated
fuel gauge. Charging can inflate voltage. Startup samples may take seconds
to settle. The patch does not add Bluetooth raw-HID support.

## Reader and tests

From the repo root:

```sh
python3 keyboard_probe.py --seconds 12         # receiver pushes + identity
python3 keyboard_probe.py --pull --seconds 12  # also one direct-USB A4 query
python3 -m unittest discover -s tests -v
```

Only Keychron raw32 vendor interfaces for the K2 HE/Link-KM are opened.
No keyboard keystrokes are stored. The reader validates report size, percent,
voltage, transport and charging values. A missing reading remains unknown.
The receiver may need a temporary per-device ACL; do not grant all hidraw nodes.
A reported receiver slot confirms pairing/connection, not battery support.

## Build

The exact QMK base is `57e682caa0a821e6de1b589e6f983f266151ab02`
(branch `2025q3`, keyboard version 1.2.1). Unmodified and patched ANSI builds
both compiled locally using the official `ghcr.io/qmk/qmk_cli` container.
Python/GJS tests: 13 passing before flashing. The patch applies cleanly to
that source. It is experimental firmware; hardware results are recorded below
when available. The installer does not install or flash it automatically.

Use a fresh checkout and QMK's build environment:

```sh
git clone https://github.com/Keychron/qmk_firmware.git qmk-firmware
cd qmk-firmware
git checkout 57e682caa0a821e6de1b589e6f983f266151ab02
git submodule update --init --depth 1 lib/chibios lib/chibios-contrib lib/printf lib/lufa
git apply /absolute/path/to/keychron-vitals/research/firmware/k2-he-battery-telemetry.patch
make keychron/k2_he/ansi:keychron
```

Do not use a K10 HE or Q1 HE image on a K2 HE. The test changes the firmware
version from 1.1.0 to the patched 1.2.1 source base; settings/calibration may
need attention. Export important Launcher settings before future experiments.

## Local flash procedure

1. Verify the wired keyboard USB id and layout before bootloader mode.
2. Unplug USB, select Cable, hold Esc, reconnect USB, release Esc.
3. Inspect `dfu-util -l`. The tested keyboard has DFU `0483:df11`, serial
   `<keyboard-serial>`, 256 KiB internal flash, address `0x08000000`.
4. Upload a full read-only backup before any write. Never use an unprotect
   operation if upload fails; it can erase flash. This internal backup does
   not include external EEPROM.
5. Build the test image from the original flash, replacing only ELF load
   segments (vectors and application). Retain the reserved gap and trailing
   contents. Keep this device-specific image and backup private.
6. Write only internal flash alternate 0. Do not write option bytes, OTP,
   device features, or change protection. Read it back and compare bytes.
7. Reconnect normally and check firmware/feature responses and A4 over USB.
8. Switch to 2.4 GHz and check unsolicited A4 packets against Fn+B LEDs.
   Check charge state, normal typing, sleep/wake and reconnect behavior.

Temporary HID ACLs disappear on unplug. DFU is a separate USB node with its own
permissions. A local user can grant temporary access with `setfacl` to the
specific verified device instead of giving an agent a sudo password.

## Licensing and attribution

The firmware patch is GPL-2.0-or-later as a derivative of Keychron/QMK and
informed by OutersGIT's GPL firmware modifications. See `firmware/LICENSE`.
Other repository files retain the repository's MIT license. Reference commits:

- Keyboard Companion: `c22739c5f2ffde97c0ff3923cdea6d578fcd44a1`
- K10 HE battery firmware: `171323703cb92ac6278eab4eb9a565baa4fc0749`
- Keychron QMK base: `57e682caa0a821e6de1b589e6f983f266151ab02`

## Local test progress (November 7, 2026)

With explicit user authorization, the custom ANSI firmware was flashed to the
identified keyboard. A complete 256 KiB internal-flash backup succeeded first.
The image retained the original reserved gap and trailing flash outside the
firmware binary region. A full post-write
upload matched the prepared image byte for byte. No option bytes or OTP were
written. Internal-flash backups and device-specific images are retained locally,
not committed to this repository.

After a normal restart, A1 reported v1.2.1 and A2 advertised battery support.
The first USB A4 reply was 100%, 4100 mV, charging, transport USB. Because 4100 mV
is also the battery code's startup default, this response alone is not evidence
of a fresh voltage sample. Wireless measurements are checked separately.

The wireless test received six valid A4 reports at approximately two-second
intervals, showing 84–85%, 3987–3992 mV, discharging, transport 4. The changing
voltage confirms a measured value rather than the 4100 mV startup default.
The user confirmed normal typing and about 8–9 Fn+B LEDs, consistent with the
reported level. Receiver firmware was unchanged.

On returning to USB without a power cycle, the keyboard reported 99%, 4098 mV,
charging, transport 1. USB returns a real voltage after sampling, but charging
inflates the voltage-derived percentage compared with the 84–85% wireless
reading. No host-side charging correction is applied. Cold-start freshness
is not encoded in A4; the first 4100 mV report must not be treated as proof
of a completed measurement. Longer-term sleep/wake and battery drain testing
remain open; normal typing and wireless-to-USB switching were tested.

The diagnostic and patch are independent of the existing mouse service.
Keyboard readings are now integrated through `keyboard_service.py` and the
Vitals reader. The installer sets up its user unit and device permissions.
`battery.py` also reads both devices directly, without Vitals or a service.

## Reproducible backup and image preparation

After verifying the K2 HE ANSI identity and entering its DFU bootloader, inspect
`dfu-util -l`. Substitute its serial below. These examples use the internal
flash alternate only, never option bytes/OTP or unprotect operations.

```sh
dfu-util -d 0483:df11 -S YOUR_KEYBOARD_SERIAL -a 0 -s 0x08000000:262144 -U original-flash.bin
python3 research/firmware/prepare_image.py original-flash.bin /path/to/qmk-firmware/.build/keychron_k2_he_ansi_keychron.elf test-image.bin
dfu-util -d 0483:df11 -S YOUR_KEYBOARD_SERIAL -a 0 -s 0x08000000 -D test-image.bin
dfu-util -d 0483:df11 -S YOUR_KEYBOARD_SERIAL -a 0 -s 0x08000000:262144 -U readback.bin
cmp test-image.bin readback.bin
```

The helper overlays only ELF flash load segments on the same keyboard's
backup, retaining reserved gaps and trailing contents. Its load segments were checked against the hardware readback. It excludes
the 16-byte DFU file suffix, which is file metadata rather than an ELF load
segment. The actual local test image included that suffix after the code.
Keep the backup and image private; do not commit device-specific settings.
After verification, unplug/reconnect normally. To restore the internal flash:

```sh
dfu-util -d 0483:df11 -S YOUR_KEYBOARD_SERIAL -a 0 -s 0x08000000:leave -D original-flash.bin
```

A complete internal backup still excludes external EEPROM. Back up important
Launcher settings before future tests and check calibration after flashing.
