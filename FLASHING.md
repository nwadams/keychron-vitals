# K2 HE ANSI: flashing and rollback

This guide covers the experimental battery-telemetry firmware for **Keychron
K2 HE ANSI (`3434:0e20`)**. It was tested with a Link-KM receiver (`3434:d026`).
Do not use these images on ISO/JIS variants, K10 HE, Q1 HE, or the receiver.
The app installer does not flash firmware.

The patch targets Keychron source version **1.2.1**, commit
`57e682caa0a821e6de1b589e6f983f266151ab02`. The local test upgraded a keyboard
from stock 1.1.0. Review the version change before proceeding. Export important
Launcher settings first; settings or Hall-effect calibration may need attention.
A full internal-flash backup does **not** include external EEPROM.

## 1. Prepare tools and paths

Install `git`, Python 3, `dfu-util`, and `lsusb` (usually the `usbutils` package).
For compilation, use a configured [QMK build environment](https://docs.qmk.fm/newbs_getting_started)
or Docker as shown below. Keep a mouse or another keyboard available while
this keyboard is in bootloader mode.

Start in the `keychron-vitals` checkout. Keep backups outside the Git repo:

```sh
KEYCHRON_REPO="$PWD"
QMK_DIR="$KEYCHRON_REPO/../qmk-firmware"
BACKUP_DIR="$KEYCHRON_REPO/../k2-he-flash-backups"
umask 077
mkdir -p "$BACKUP_DIR"
```

Keep these variables in the same terminal throughout this guide. Use a fresh
backup directory for each device/experiment. Do not overwrite your original
backup or commit it to Git: images can contain device-specific settings.

## 2. Build the patched firmware

Use a fresh source checkout:

```sh
git clone https://github.com/Keychron/qmk_firmware.git "$QMK_DIR"
git -C "$QMK_DIR" checkout 57e682caa0a821e6de1b589e6f983f266151ab02
git -C "$QMK_DIR" submodule update --init --depth 1 lib/chibios lib/chibios-contrib lib/printf lib/lufa
git -C "$QMK_DIR" apply --check "$KEYCHRON_REPO/research/firmware/k2-he-battery-telemetry.patch"
git -C "$QMK_DIR" apply "$KEYCHRON_REPO/research/firmware/k2-he-battery-telemetry.patch"
```

With a native QMK build environment:

```sh
make -C "$QMK_DIR" keychron/k2_he/ansi:keychron
```

Alternatively, the local test used QMK's official Docker image. This build
container has no USB devices mounted and runs without network access:

```sh
docker pull ghcr.io/qmk/qmk_cli:latest
docker run --rm --user "$(id -u):$(id -g)" --network none \
  -e HOME=/tmp -e SKIP_GIT=yes -e QMK_USERSPACE= \
  -v "$QMK_DIR:/qmk_firmware:Z" -w /qmk_firmware \
  ghcr.io/qmk/qmk_cli:latest make keychron/k2_he/ansi:keychron -j4
```

Use the resulting **ELF**, not just the downloadable `.bin`, for the
preserving-image helper:

```sh
ELF="$QMK_DIR/.build/keychron_k2_he_ansi_keychron.elf"
test -s "$ELF"
```

The helper overlays ELF flash load segments on your original backup, retaining
reserved gaps and trailing contents. It excludes DFU file-suffix metadata.

## 3. Confirm the keyboard and enter bootloader mode

Connect the keyboard with a USB **data** cable and select **Cable** mode.
Before entering DFU, confirm the model:

```sh
lsusb -d 3434:0e20
```

If the keyboard service is installed, pause it during flashing:

```sh
systemctl --user stop keychron-keyboard-battery.service
```

Enter the keyboard's bootloader:

1. Unplug the keyboard's USB cable.
2. Keep its side switch on **Cable**.
3. Hold **Esc**, reconnect USB, then release Esc.
4. Inspect the DFU device:

```sh
dfu-util -l
```

Expect `0483:df11`, alternate **0**, and an internal-flash map beginning at
`0x08000000` with **256 KiB** total. Set the serial printed for this keyboard:

```sh
KEYBOARD_SERIAL='replace-with-the-serial-from-dfu-util'
```

The generic STM32 DFU ID alone does not identify a keyboard. If the map differs,
or the intended device is ambiguous, stop and verify before writing.
If access is denied, run the specific `dfu-util` command with `sudo` in your
own terminal; the bootloader has separate permissions from normal hidraw mode.

## 4. Back up before writing

The following is a read-only upload of the keyboard's internal flash:

```sh
dfu-util -d 0483:df11 -S "$KEYBOARD_SERIAL" -a 0 \
  -s 0x08000000:262144 -U "$BACKUP_DIR/original-flash.bin"
wc -c "$BACKUP_DIR/original-flash.bin"
sha256sum "$BACKUP_DIR/original-flash.bin" > "$BACKUP_DIR/original-flash.sha256"
```

The backup must be **262144 bytes** and the upload must succeed. Keep a second
copy somewhere safe. If upload fails, stop: do not use `unprotect`, mass erase,
option-byte writes, or OTP operations to force it to work.

## 5. Prepare, flash, and verify

Prepare the image from **this keyboard's** backup and the compiled ELF:

```sh
python3 "$KEYCHRON_REPO/research/firmware/prepare_image.py" \
  "$BACKUP_DIR/original-flash.bin" "$ELF" "$BACKUP_DIR/test-image.bin"
sha256sum "$BACKUP_DIR/test-image.bin"
```

The helper refuses to overwrite an existing output. Do not substitute another
keyboard's backup. Flash only internal-flash alternate 0:

```sh
dfu-util -d 0483:df11 -S "$KEYBOARD_SERIAL" -a 0 \
  -s 0x08000000 -D "$BACKUP_DIR/test-image.bin"
```

Leave the keyboard in DFU and read all flash back:

```sh
dfu-util -d 0483:df11 -S "$KEYBOARD_SERIAL" -a 0 \
  -s 0x08000000:262144 -U "$BACKUP_DIR/test-readback.bin"
cmp "$BACKUP_DIR/test-image.bin" "$BACKUP_DIR/test-readback.bin"
```

`cmp` should print nothing and exit successfully. If it differs, keep the
backup and logs and investigate or roll back before using the test firmware.
After verification, unplug/reconnect normally **without holding Esc**.

## 6. Test battery reporting

In Cable mode, allow voltage sampling to settle, then run:

```sh
python3 "$KEYCHRON_REPO/battery.py" --device keyboard
```

Next unplug USB, select 2.4 GHz, wake the keyboard, and run the same command.
The keyboard should push reports about every two seconds. Compare the unplugged
percentage with **Fn+B** LEDs, and check typing, charging state, reconnect,
and sleep/wake behavior.

Charging can inflate the voltage-derived percentage. An early report of
100% / 4100 mV may be the firmware startup default, not a completed measurement.
The local test confirmed changing wireless voltage, consistent Fn+B LEDs,
normal typing, and USB charging; long-term sleep/wake remains untested.

If installed, resume monitoring:

```sh
systemctl --user start keychron-keyboard-battery.service
systemctl --user status keychron-keyboard-battery.service
```

Firmware flashing alone does not require a GNOME logout. Log out/in only when
loading changed Vitals extension JavaScript.

## 7. Roll back to your original firmware

Repeat the Cable + Esc procedure to enter DFU. Recheck `dfu-util -l` and select
the same keyboard serial. Verify your original backup has not changed:

```sh
sha256sum -c "$BACKUP_DIR/original-flash.sha256"
```

Restore its complete internal flash, then read it back before reconnecting:

```sh
dfu-util -d 0483:df11 -S "$KEYBOARD_SERIAL" -a 0 \
  -s 0x08000000 -D "$BACKUP_DIR/original-flash.bin"
dfu-util -d 0483:df11 -S "$KEYBOARD_SERIAL" -a 0 \
  -s 0x08000000:262144 -U "$BACKUP_DIR/rollback-readback.bin"
cmp "$BACKUP_DIR/original-flash.bin" "$BACKUP_DIR/rollback-readback.bin"
```

When comparison succeeds, unplug/reconnect normally. Check typing, settings,
and calibration. This restores internal flash, not external EEPROM changes
made after the backup.

Stock firmware will no longer provide the custom A4 battery reports. Disable
the keyboard monitor if desired; the mouse service can keep running:

```sh
systemctl --user disable --now keychron-keyboard-battery.service
```

In Vitals, unpin the K2 HE row and select **Keychron M3 Lite** under Battery
Preferences → Display Battery if you want the mouse as the summary.

If the original backup is unavailable, obtain stock firmware specifically for
**K2 HE ANSI** from official Keychron support/Launcher. That reinstalls stock
firmware but cannot recreate your original device-specific internal settings.
For a keyboard that will not type, try the Cable + Esc bootloader procedure
again and check for DFU before attempting recovery; bootloader availability
is not guaranteed by this patch.

See [the investigation and hardware results](research/KEYBOARD.md) for protocol
and source details.
