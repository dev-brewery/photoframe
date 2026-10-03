> This is a community-maintained fork of [mrworf/photoframe](https://github.com/mrworf/photoframe).
> The original project appears to be unmaintained. This fork adds Python 3 support, [Immich](https://immich.app/) integration, modern display handling, and more.

# photoframe

Raspberry Pi software that displays photos from your personal photo collection on an attached screen, like a digital photo frame. Supports [Immich](https://immich.app/) (self-hosted), Google Photos (deprecated), USB storage, and simple URL sources.

## why use this as opposed to buying one?

Unlike most commercial frames, this one automatically refreshes content from your photo collection. Uses keywords/albums so you control exactly what's shown. Runs on your own hardware with no cloud dependency (when using Immich or USB).

It also has features like ambient color temperature adjustment, ambient light powersave, scheduled display hours, and a web-based configuration interface.

## features

- **Immich integration** - display photos from your self-hosted [Immich](https://immich.app/) server (recommended)
- **HEIC/HEIF support** - display Apple photos without conversion issues
- **Python 3** - modern, maintained codebase
- **Works without tvservice** - on current Raspberry Pi OS, where `tvservice` is gone, the display size is read from the framebuffer; where the `tvservice` command is installed, it is still used
- **Multi-architecture** - supports both 32-bit (armhf) and 64-bit (arm64) Raspberry Pi OS
- Simple web interface for configuration (port 7777)
- Google Photos search integration (deprecated due to API changes - [details](GOOGLE_PHOTOS.md))
- USB storage photo source
- Blanking of screen (scheduled off hours)
- Ambient color temperature adjustment (TCS34725 sensor)
- Ambient light powersave
- Power control via GPIO (turn RPi on/off)
- Non-HDMI displays (SPI, DPI, etc)
- Display health validation and diagnostics

## requirements

- Raspberry Pi (Zero, Zero 2W, 1, 3, 4, or 5)
- Display (HDMI or SPI/DPI)
- Python 3
- Photo source: [Immich](https://immich.app/) server, USB storage, or URL source
- Internet (for Immich; not required for USB)

## installation

### Option 1: Fresh install script (recommended for new setups)

On a clean Raspberry Pi OS (Bullseye, Bookworm or Trixie):

```bash
sudo apt-get update -y && sudo apt upgrade -y
sudo apt install -y git
sudo su -
git clone https://github.com/dev-brewery/photoframe.git /root/photoframe
cd /root/photoframe
./install.sh
systemctl start frame.service
```

The installer handles all dependencies, service setup, and auto-update configuration. It does not start the service; the last line above does, and it starts on its own at every boot from then on. The web UI is then available at `http://<your-pi-ip>:7777`.

A script install has no web UI login: anyone on your network can open the page. To add one, see [web UI login](#web-ui-login).

### Option 2: SD card image (recommended for first-time users)

Pre-built Raspberry Pi OS Lite images with photoframe preinstalled are attached to releases on the [photoframe releases page](https://github.com/dev-brewery/photoframe/releases). Flash, edit two files on the boot partition, boot, done. The image is built by the [`dev-brewery/pi-gen`](https://github.com/dev-brewery/pi-gen) fork (branch `bookworm-photoframe`) — see its [`HISTORY.md`](https://github.com/dev-brewery/pi-gen/blob/bookworm-photoframe/HISTORY.md) for how the image is produced if you want to rebuild from source.

**Step 1 — flash the image.** Download the `image_*-lite.zip` asset from the releases page and flash with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (recommended), [Balena Etcher](https://etcher.balena.io/), [Rufus](https://rufus.ie/) in DD mode, or `dd` on Linux/Mac. In Raspberry Pi Imager, choose **"Use custom"** and point at the `.zip`.

**Do not use Imager's gear icon / advanced settings** — those are greyed out for custom images, and the image already has its own mechanisms for every setting Imager would configure. Just flash it.

**Step 2 — configure WiFi.** After Imager finishes, the SD card's `bootfs` partition is visible in Windows Explorer (or as `/Volumes/bootfs` on macOS, or auto-mounted on Linux). Open **`wifi-config.txt`** in a text editor that preserves Unix line endings (Notepad++, VS Code, `nano`, or `vim` — **not** regular Windows Notepad, which mangles line endings). Fill in your network:

```ini
[wifi]
SSID=YourNetworkName
PSK=YourPassword
COUNTRY=US
```

Set `COUNTRY` to your ISO 3166-1 alpha-2 code (`GB`, `DE`, `CA`, `JP`, ...) if you're outside the US. Save the file. On first boot, the Pi reads this file, connects to your WiFi, and renames the file to `wifi-config.txt.applied` so you know it worked. If something goes wrong, a `wifi-config.txt.error` file appears with the reason.

**Step 3 (optional) — force a custom display resolution.** Most HDMI monitors are auto-detected via EDID and need no configuration. If you're driving an atypical panel — e.g., an HDMI-to-LVDS adapter board feeding an old laptop LCD — edit **`cmdline.txt`** on the same `bootfs` partition and append the video mode to the single existing line (with a leading space, no newlines):

```
 video=HDMI-A-1:1366x768MR@60D
```

Replace `1366x768` with your panel's native resolution. Flag meanings: `M` = CVT timings, `R` = reduced blanking, `@60` = refresh rate, `D` = force DVI output and treat the port as connected even without HPD (needed for most HDMI-to-LVDS adapter boards, which don't assert HPD). On Bookworm's KMS driver, the legacy `hdmi_group` / `hdmi_mode` / `hdmi_cvt` options in `config.txt` are silently ignored — `cmdline.txt` is the only file that works.

**Step 4 — eject and boot.** Safely eject the SD card from your computer, insert it into the Pi, and power on. Within 30 seconds the photoframe service starts, WiFi associates, and the frame is reachable on your network at `http://<pi-ip>:7777`.

**Step 5 — SSH in and change the password.** The image ships with a default account so you can manage the Pi without any setup:

- **Username:** `photoframe`
- **Password:** `photoframe`

From any computer on the same network:

```bash
ssh photoframe@<pi-ip>
passwd    # change the password immediately on first login
```

If you'd rather use a different username, create one and remove the default after logging in:

```bash
sudo adduser yourname
sudo usermod -aG sudo yourname
# log out, log back in as yourname, then:
sudo deluser --remove-home photoframe
```

The web UI has its own login, separate from SSH. On the image it is `photoframe` / `password`, stored in `http-auth.json` on the boot partition. See [web UI login](#web-ui-login) for how to change it.

The image's time zone is `Europe/London`. Choose your own under **Time zone** on the web UI, so that the scheduled on and off hours match your clock.

### Option 3: Manual install

See [MANUAL.md](MANUAL.md) for a step-by-step walkthrough that mirrors what `install.sh` does, for users who want to understand every step or reproduce it on a system where the scripted path doesn't fit.

### Option 4: Migrate from mrworf/photoframe

If you're running the original mrworf version, see [MIGRATION.md](MIGRATION.md) for step-by-step instructions to switch to this fork.

## web UI login

The web UI uses HTTP basic authentication when it finds a file named `http-auth.json`:

```json
{"user": "photoframe", "password": "password"}
```

At startup photoframe looks in these places, in this order, and uses the first file that has both keys:

1. `/boot/http-auth.json`
2. `/boot/firmware/http-auth.json`
3. `/root/photoframe_config/http-auth.json`

If it finds none, the web UI has no login and the log says `No http-auth.json found, disabling http authentication`.

- **SD card image:** ships `/boot/firmware/http-auth.json` with `photoframe` / `password`. Change it by editing that file, either on the Pi or as `http-auth.json` on the `bootfs` partition with the card in your computer. A file in `/root/photoframe_config/` is not used while the boot-partition file exists.
- **`install.sh` and manual installs:** no file is created. Create `/root/photoframe_config/http-auth.json` yourself.

The file is read when the service starts, so restart after changing it: `sudo systemctl restart frame.service`.

## quick start with Immich

1. Open the web UI at `http://<your-pi-ip>:7777`
2. Select **Immich** from the dropdown and click **Add photo provider**
3. Click **Enter Credentials** and give your server URL and API key, or upload them as a JSON file (see [README-Immich.md](README-Immich.md))
4. Click **Browse** to pick an album, then **Add**

For detailed Immich setup instructions, see [README-Immich.md](README-Immich.md).

## differences from upstream (mrworf/photoframe)

| Feature | mrworf/photoframe | dev-brewery/photoframe |
|---------|-------------------|------------------------|
| Python version | Python 2 | **Python 3** |
| Immich support | No | **Yes** |
| HEIC/HEIF images | No | **Yes** |
| Display detection | tvservice only | **tvservice, or the framebuffer (`fbset`) where tvservice is missing** |
| Pi 4/5 support | Limited | **Full (armhf + arm64)** |
| Google Photos | Functional (pre-API change) | Deprecated (API removed by Google) |
| Picasa Web | Present (non-functional) | Removed |

## color temperature

Photoframe can adjust image color temperature to match room lighting using a TCS34725 sensor (e.g., [Adafruit TCS34725](https://www.adafruit.com/product/1334)).

Wiring:
```
3.3V -> Pin 1 (3.3V)
SDA  -> Pin 3 (GPIO 2)
SCL  -> Pin 5 (GPIO 3)
GND  -> Pin 9 (GND)
```

Enable I2C via `raspi-config` (Interfaces > I2C). Then download the ImageMagick color temperature script from http://www.fmwconcepts.com/imagemagick/colortemp/index.php, save as `/root/photoframe_config/colortemp.sh`, and make executable (`chmod +x`).

The sensor is auto-detected. Once working, the web UI shows white balance (kelvin) and light (lux) readings.

**Tip:** Ground the LED pin on the Adafruit board (connect to Pin 9) to disable the bright onboard LED.

### ambient powersave

Using the same sensor, set a light threshold and duration in the web UI. If ambient light stays below the threshold for the configured duration, the display powers off. The scheduler takes priority over the sensor during off hours.

## power on/off

Photoframe watches one GPIO pin and shuts the Pi down cleanly when a momentary switch connects that pin to ground.

The pin is the **GPIO to monitor for shutdown interrupts** setting on the web UI. A new install starts on `auto`, which chooses the pin each time the service starts:

| Color sensor (TCS34725) | Pin used | Wire the switch between |
|-------------------------|----------|-------------------------|
| Not found | GPIO 3 | pin 5 (GPIO 3) and pin 6 (GND) |
| Found | GPIO 26 | pin 37 (GPIO 26) and pin 39 (GND) |

GPIO 3 is the sensor's I2C clock line, which is why a frame with the sensor uses GPIO 26 instead. Connecting GPIO 3 to ground is also what wakes a halted Raspberry Pi on models that have that feature, so there the same switch turns the frame back on. GPIO 26 only shuts it down.

A frame that already has a pin number saved keeps that number. The settings page accepts only numbers, so to go back to `auto` use the API (add `-u <user>:<password>` if the web UI has a login):

```bash
curl -X PUT http://<pi-ip>:7777/setting/shutdown-pin/auto
```

## FAQ

### How do I get SSH access?

It depends on which install path you used.

**If you flashed the SD card image (Option 2):** SSH is enabled out of the box and the image ships with a default account so you can get in from any OS (Windows, macOS, Linux) without extra setup:

- **Username:** `photoframe`
- **Password:** `photoframe`

```bash
ssh photoframe@<your-pi-ip>
```

**Change the password immediately on first login:**

```bash
passwd
```

If you'd rather use a different username, create one and remove the default after logging in:

```bash
sudo adduser yourname
sudo usermod -aG sudo yourname
# log out, log back in as yourname, then:
sudo deluser --remove-home photoframe
```

**If you installed via `install.sh` on a fresh Raspberry Pi OS (Option 1):** SSH and user accounts are whatever you configured when flashing Raspberry Pi OS itself. If you used Raspberry Pi Imager's advanced settings (gear icon) to set a username, password, and enable SSH, you're already set — just `ssh <youruser>@<your-pi-ip>`. Otherwise, enable SSH on the Pi with `sudo raspi-config` (Interfaces → SSH), or place an empty file named `ssh` on the boot partition before first boot.

Avoid modifying files in `/root/photoframe/` directly, as this will prevent automatic updates via `update.sh`.

### My display shows nothing or the wrong resolution

Most HDMI monitors are auto-detected via EDID. If you're driving an atypical panel (e.g. an HDMI-to-LVDS adapter board feeding a laptop LCD) that doesn't report EDID, you'll need to force the mode manually. The right place to do this depends on which Raspberry Pi OS release you're on, because Bookworm and Bullseye use different display stacks.

**On Bookworm (KMS driver):** custom modes go on the kernel command line, not in `config.txt`. Legacy `hdmi_group` / `hdmi_mode` / `hdmi_cvt` / `hdmi_force_hotplug` settings in `config.txt` are silently ignored under the `vc4-kms-v3d` driver.

```bash
sudo nano /boot/firmware/cmdline.txt
```

`cmdline.txt` is a single line — do not add newlines. Append (with a leading space):

```
video=HDMI-A-1:1366x768MR@60D
```

Replace `1366x768` with your panel's native resolution. Flag meanings: `M` = CVT timings, `R` = reduced blanking, `@60` = refresh rate, `D` = force DVI-style output and treat the port as connected even without HPD (required because most adapter boards don't assert HPD). Reboot to apply.

**On Bullseye (legacy firmware display path):** the traditional `config.txt` knobs still work.

```bash
sudo nano /boot/config.txt
```

Add:

```
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1366 768 60 3 0 0 1
```

Replace `1366 768` with your panel's native resolution. `hdmi_mode=87` is the "use custom CVT" slot that activates `hdmi_cvt`; `hdmi_force_hotplug=1` is required because most driver boards don't assert HPD. Reboot to apply.

### The picture became enlarged and cut off after I re-plugged the HDMI cable

Reboot the frame with the cable connected.

Seen on a Raspberry Pi 4 on Bookworm: when the HDMI cable is unplugged and plugged back in while the frame is running, the Pi can fail to re-read the monitor's identification (EDID) and drops the screen to 1024x768. The framebuffer photoframe draws into keeps the size it was given at boot, so the screen shows only its top-left part. A reboot reads the monitor again and sizes the screen and the framebuffer correctly.

### Are there logs?

On Bookworm: `journalctl -u frame.service -f`, or the **Log report** button in the System box of the web UI, which shows the last 100 lines. It reads `journalctl` automatically when there is no traditional log file such as `/var/log/syslog`; Bookworm Lite doesn't ship `rsyslog`.

On older releases that still have `rsyslog`: `/var/log/syslog` works too (search for `frame` or `photoframe`).

For verbose debug output:

```bash
sudo systemctl stop frame.service
/root/photoframe/frame.py --debug
```

### How do I test on a desktop?

Run `frame.py` with `--emulate` to run without RPi hardware.

### How do I build my own SD card image?

Check out the `bookworm-photoframe` branch on https://github.com/dev-brewery/pi-gen for the pi-gen configuration used to build release images. The [`build-image.yml`](.github/workflows/build-image.yml) workflow in this repo runs that same build in CI and attaches the resulting `.zip` to the release for the tag being built.

Release builds fire automatically on `v[0-9]*.[0-9]*.[0-9]*` tag push and resolve the pi-gen ref from the photoframe tag name (pi-gen tag names mirror photoframe tag names 1:1). To rebuild an image manually:

```
gh workflow run build-image.yml \
  -f tag=v3.0.0-rc1 \
  -f pi_gen_ref=v3.0.0-rc1
```

Both inputs are required — there is no default. For a byte-for-byte rebuild of a released image, pass the same tag name for both. For testing an unreleased photoframe branch against a specific pi-gen commit, pass a branch or SHA for `pi_gen_ref`.

### USB sticks not recognized?

Install exFAT support: `sudo apt install exfat-fuse exfat-utils`

### How does "Refresh keywords" work?

Photo lists refresh when: (1) all photos have been shown, (2) "Forget Memory" is pressed in the web UI, or (3) the configured refresh interval expires. Set to 0 to disable timed refresh.

### What about photoframe.sensenet.nu?

This service handles OAuth redirect for Google Photos authorization behind firewalls. Since Google Photos is now deprecated, this is only relevant for legacy setups. See `extras/` if you want to self-host.

## license

[GNU General Public License v2.0](LICENSE)

Originally created by [mrworf](https://github.com/mrworf). Community maintained by [dev-brewery](https://github.com/dev-brewery).
