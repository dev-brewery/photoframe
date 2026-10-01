# Manual installation (Raspberry Pi OS Bookworm + Python 3)

> **Most users should not read this document.** The two easier paths:
>
> 1. Download the pre-built SD card image from the [releases page](https://github.com/dev-brewery/photoframe/releases), flash, edit `wifi-config.txt`, boot. Covered as Option 2 in the [README](README.md).
> 2. Run [`install.sh`](install.sh) on a fresh Raspberry Pi OS Lite install. Covered as Option 1 in the README.
>
> This document is for users who want to understand every step, or who need to reproduce the install on a system where the scripted path doesn't fit. Everything here is also documented in `install.sh` as executable code.
>
> The pre-Bookworm install process (minibian, Python 2, `/etc/network/interfaces`) is no longer supported and is preserved only in git history (`git log -- MANUAL.md` against earlier refs).

First, install **Raspberry Pi OS Lite (Bookworm)** on your SD card using
[Raspberry Pi Imager](https://www.raspberrypi.com/software/). The Lite
variant is the right choice — photoframe is a framebuffer application
and writes directly to `/dev/fb0`, so a desktop environment would
actively compete with it for the display. Do **not** use Desktop or Full.

When Imager offers its "advanced settings" gear icon, use it to set:
- **Username and password** (anything you like — these are yours)
- **SSH enabled**
- **WiFi credentials** and the **WiFi country code**
- **Hostname** (optional, defaults to `raspberrypi`)
- **Locale and timezone**

Imager bakes these into the image before writing, so when you boot,
the Pi is on your WiFi with SSH ready. If you skip the gear icon, you
will need to configure WiFi and SSH manually after boot, which this
guide covers in the `# wifi setup` section below.

Photoframe and its dependencies require about **1 GB** of space.
Bookworm Lite is about 3 GB after first boot, so a 4 GB SD card is the
absolute minimum — 8 GB or larger is comfortable.

Make your install up to date by issuing

```
sudo apt update && sudo apt upgrade
```

Once done, install all dependencies. The package list below is lifted
from `stage2/04-photoframe/00-packages` in the
[`dev-brewery/pi-gen`](https://github.com/dev-brewery/pi-gen) fork and
matches exactly what the pre-built image ships with:

```
sudo apt install apt-utils raspi-config git bc openssh-server \
    python3 python3-pip python3-smbus \
    fbset imagemagick libheif-examples libjpeg-turbo-progs \
    rng-tools-debian
```

**Python 3 note:** Bookworm enforces
[PEP 668](https://peps.python.org/pep-0668/) and refuses `pip` installs
into the system Python environment without explicit opt-in. Photoframe
needs its dependencies globally installed (the `frame` systemd service
runs them as root), so we pass the `--break-system-packages` flag when
running pip. This is intentional, not a mistake. See the photoframe
install command block below.

Next, let's tweak the boot config so the framebuffer is free for
photoframe to take over. On Bookworm, the boot-partition config files
live at `/boot/firmware/`, not `/boot/` (which was the Bullseye-era
path). Edit **`/boot/firmware/config.txt`** and add:

```
disable_splash=1
framebuffer_ignore_alpha=1
```

If you plan to use the TCS34725 color-temperature sensor (see the
README's `color temperature?` section), also add:

```
dtparam=i2c_arm=on
```

**Atypical HDMI displays:** if you're driving a non-standard panel —
for example, an old laptop LCD via an HDMI-to-LVDS adapter board that
doesn't report a proper EDID — you need to force a specific video mode
on the kernel command line. Edit **`/boot/firmware/cmdline.txt`** (a
single-line file; do NOT add newlines) and append this to the end of
the existing line, with a leading space:

```
video=HDMI-A-1:1366x768MR@60D
```

Replace `1366x768` with your panel's native resolution. Flag meanings:
`M` = CVT timings, `R` = reduced blanking, `@60` = refresh rate,
`D` = force DVI output and treat the port as connected even without
HPD (required because most HDMI-to-LVDS adapter boards don't assert
HPD). On Bookworm's KMS driver, the legacy `hdmi_group` / `hdmi_mode`
/ `hdmi_cvt` options in `config.txt` are **silently ignored** — the
only file that matters for forcing a video mode is `cmdline.txt`.

**If you have a normal HDMI monitor**, skip the cmdline.txt edit
entirely. EDID auto-detection works correctly for the overwhelming
majority of displays.

We also want to disable the first console (since that's going to be
our frame) and mask the boot splash:

```
sudo systemctl disable getty@tty1.service
sudo systemctl mask plymouth-start.service
```

Both are needed. `getty@tty1.service` would otherwise print a login
prompt on the framebuffer, and `plymouth-start.service` would flash a
Raspberry Pi boot splash that fights photoframe for the display.

Set the timezone so the on/off hours schedule makes sense:

```
sudo timedatectl set-timezone America/Los_Angeles
```

If you don't know your timezone, list all supported values:

```
timedatectl list-timezones
```

Finally, install photoframe. The repo to clone is
`dev-brewery/photoframe` (the maintained fork), not the original
`mrworf/photoframe` which is unmaintained and pre-Python-3.

```
sudo su -
cd /root
git clone https://github.com/dev-brewery/photoframe.git
cd photoframe
pip3 install --break-system-packages -r requirements.txt
cp frame.service /etc/systemd/system/
systemctl enable /etc/systemd/system/frame.service
```

Add the `i2c-dev` kernel module to `/etc/modules` so the color sensor
(if you're using one) works on next boot:

```
grep -q '^i2c-dev$' /etc/modules || echo 'i2c-dev' >> /etc/modules
```

And reboot:

```
reboot
```

Done! Once the device has rebooted, the photoframe web UI is hosted on
port 7777. Find the Pi's IP address (check your router's DHCP table or
try `ping raspberrypi.local` if your network supports mDNS), then open
`http://<pi-ip>:7777` in your browser. The default web UI credentials
are `photoframe` / `password` (change via `http-auth.json` in
`/root/photoframe_config/`). Choose your photo service (Immich is the
supported default; Google Photos is deprecated) and follow the prompts.

# wifi setup

**Bookworm uses NetworkManager** for all network configuration. The
legacy `/etc/network/interfaces` + `wpa_supplicant.conf` approach that
the original MANUAL.md documented is no longer supported — those files
exist but are not read by the active network stack on a standard
Bookworm Lite install. If you want to configure WiFi from scratch on
a Bookworm system, use NetworkManager.

**The easiest path** is Raspberry Pi Imager's gear icon during initial
flashing. See the note at the top of this document.

**If you skipped the gear icon** and need to configure WiFi after boot,
you have two options:

## Option A: Interactive via `nmtui`

This is the friendliest manual path. Connect a keyboard and display
directly to the Pi, or SSH in over a wired ethernet connection, then:

```
sudo nmtui
```

Choose "Activate a connection" → pick your SSID → enter the password.
NetworkManager creates and stores the profile automatically; it will
auto-connect on every subsequent boot. To confirm it's working:

```
nmcli connection show --active
```

You should see your WiFi connection listed.

## Option B: Command-line via `nmcli`

Non-interactive, scriptable:

```
sudo nmcli device wifi connect "<your-ssid>" password "<your-password>"
```

NetworkManager creates the profile and activates it immediately. For
networks with non-ASCII or special characters in the SSID or password,
wrap each value in single quotes to avoid shell-quoting confusion.

## Regulatory domain (country code)

**Important:** without a configured regulatory domain, the kernel's
`cfg80211` module will refuse to transmit on any WiFi channel, and
`nmcli device wifi list` returns empty. Bookworm Lite ships without
a default country set.

Set your country via `raspi-config` (interactive):

```
sudo raspi-config
```

Navigate to **Localisation Options** → **WLAN Country** → select your
country code (e.g., `US`, `GB`, `DE`, `JP`). Exit; the change takes
effect immediately, though a reboot is the safest way to confirm.

**Non-interactive equivalent:**

```
sudo raspi-config nonint do_wifi_country US
```

Replace `US` with your ISO 3166-1 alpha-2 code.

## Disabling ethernet once WiFi is working

If you configured WiFi over an initial wired connection and now want
the Pi to boot headless on WiFi only, you do **not** need to disable
the ethernet interface — NetworkManager handles both concurrently
without conflict. The old `raspi-config` "wait for network" workaround
described in MANUAL.md is not needed on Bookworm; systemd's default
network-online target timeout is sensible. Just unplug the ethernet
cable when you're done, and the Pi will continue to work on WiFi.

# faq

## I want it to auto-update

Schedule a cronjob to run `update.sh`. It uses git to pull changes (if
any) and restarts the service when it updates. The pre-built image
from the releases page already schedules this at 3:15 AM daily via
`/etc/crontab`. For a manual install, add the line yourself:

```
echo "15 3    * * *   root    /root/photoframe/update.sh" | \
    sudo tee -a /etc/crontab
```

## How do I change the SSH password after install?

Log in as the user you created (or the default `photoframe` user on
the pre-built image) and run:

```
passwd
```

Then enter the old password and the new one twice. Do this **on first
login** if you're using the pre-built image with default credentials.

## My WiFi isn't connecting even though the credentials are right

Three likely causes, in order of probability:

1. **Regulatory domain not set.** Check with `sudo iw reg get`. If it
   shows `country 00: DFS-UNSET`, run `sudo raspi-config nonint do_wifi_country US`
   (or your country code) and reboot.
2. **5 GHz network on a Pi Zero W.** The Pi Zero W and Zero 2 W only
   support 2.4 GHz. If your router broadcasts separate 2.4 GHz and
   5 GHz SSIDs, connect to the 2.4 GHz one. If it broadcasts a single
   dual-band SSID, the Pi should negotiate 2.4 GHz automatically.
3. **Wrong password.** Obvious but common. NetworkManager's failure
   mode for a bad password is a `No secrets` error in `journalctl -u
   NetworkManager -b 0`.

## How does the pre-built image compare to this manual install?

The pre-built image from the releases page is produced by the
[`dev-brewery/pi-gen`](https://github.com/dev-brewery/pi-gen) fork on
branch `bookworm-photoframe`. It does everything this guide does, plus:

- Bakes in the `photoframe` / `photoframe` default user (change
  immediately via `passwd` on first login)
- Ships with `WPA_COUNTRY=US` as the default regulatory domain
- Provides a `wifi-config.txt` file on the boot partition you can edit
  on Windows before first boot for headless WiFi setup
- Skips the stage3/4/5 desktop builds that would conflict with
  photoframe's framebuffer takeover

If you're producing an image for distribution to non-technical users,
use the pi-gen fork instead of the manual install. See
[`HISTORY.md`](https://github.com/dev-brewery/pi-gen/blob/bookworm-photoframe/HISTORY.md)
in the pi-gen fork for the full story of why each of those defaults
was chosen.

## How do I test and develop on a desktop?

Start `frame.py` with `--emulate` to run without an RPi. The emulator
mode is useful for iterating on the web UI and photo-service code
without needing to reflash a card every time.

# HTTP API

Photoframe exposes HTTP endpoints for automation and scripting. All
endpoints require HTTP Basic authentication with the credentials from
`/root/photoframe_config/http-auth.json`.

## Display control

The display can be turned on and off via HTTP, useful for home
automation integration (Home Assistant, Domoticz, etc.):

```bash
# Turn screen off
curl -u photoframe:password http://<pi-ip>:7777/control/screenoff

# Turn screen on
curl -u photoframe:password http://<pi-ip>:7777/control/screenon
```

Both return JSON: `{"screen": "on", "success": true}` or
`{"screen": "off", "success": true}`.

**Note:** This is API groundwork for a future persistent manual override
feature. Currently, schedule and ambient light sensor rules continue to
run and may revert the display state on the next evaluation cycle (up to
60 seconds). A future release will add the ability to hold a manual
override until explicitly cleared.

## Configuration backup and restore

Export your entire configuration to a `.tar.gz` file:

```bash
curl -u photoframe:password \
    http://<pi-ip>:7777/backup/export \
    -o photoframe-config-backup.tar.gz
```

Restore configuration from a backup file:

```bash
curl -u photoframe:password \
    -F "filename=@photoframe-config-backup.tar.gz" \
    http://<pi-ip>:7777/backup/import
```

The import endpoint validates the backup before restoring:
- Rejects archives containing path traversal (`..` or absolute paths)
- Requires a `settings.json` file in the archive
- Creates a `.bak` copy of the current config before overwriting
- Stops the slideshow during restore and restarts it after
