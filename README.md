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
- **Modern display detection** - automatic fallback from KMS/DRM to xrandr to fbset to tvservice
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

On a clean Raspberry Pi OS (Bookworm or Bullseye):

```bash
sudo su -
git clone https://github.com/dev-brewery/photoframe.git /root/photoframe
cd /root/photoframe
chmod +x install.sh
./install.sh
```

The installer handles all dependencies, service setup, and auto-update configuration. After installation, the web UI is available at `http://<your-pi-ip>:7777`.

Default credentials: `photoframe` / `password` (change via `http-auth.json` in `/root/photoframe_config/`)

### Option 2: SD card image

Download from the [releases page](https://github.com/dev-brewery/photoframe/releases), flash to SD card with [Rufus](https://rufus.ie/), [Balena Etcher](https://etcher.balena.io/), or `dd`.

1. Flash image to SD card
2. Edit `wifi-config.txt` on the `boot` partition with your WiFi credentials
3. Boot the Pi and follow the on-screen instructions

### Option 3: Migrate from mrworf/photoframe

If you're running the original mrworf version, see [MIGRATION.md](MIGRATION.md) for step-by-step instructions to switch to this fork.

## quick start with Immich

1. Open the web UI at `http://<your-pi-ip>:7777`
2. Select **Immich** from the dropdown and click **Add photo service**
3. Upload a JSON config with your server URL and API key (see [README-Immich.md](README-Immich.md))
4. Add album names as keywords

For detailed Immich setup instructions, see [README-Immich.md](README-Immich.md).

## differences from upstream (mrworf/photoframe)

| Feature | mrworf/photoframe | dev-brewery/photoframe |
|---------|-------------------|------------------------|
| Python version | Python 2 | **Python 3** |
| Immich support | No | **Yes** |
| HEIC/HEIF images | No | **Yes** |
| Display detection | tvservice only | **KMS/DRM + xrandr + fbset + tvservice fallback** |
| Pi 4/5 support | Limited | **Full (armhf + arm64)** |
| Google Photos | Functional (pre-API change) | Deprecated (API removed by Google) |
| Picasa Web | Present (non-functional) | Removed |

## color temperature

Photoframe can adjust image color temperature to match room lighting using a TCS34725 sensor (e.g., [Adafruit TCS34725](https://www.adafruit.com/product/1334)).

Wiring:
```
3.3V -> Pin 1 (3.3V)
SDA  -> Pin 3 (GPIO 0)
SCL  -> Pin 5 (GPIO 1)
GND  -> Pin 9 (GND)
```

Enable I2C via `raspi-config` (Interfaces > I2C). Then download the ImageMagick color temperature script from http://www.fmwconcepts.com/imagemagick/colortemp/index.php, save as `/root/photoframe_config/colortemp.sh`, and make executable (`chmod +x`).

The sensor is auto-detected. Once working, the web UI shows white balance (kelvin) and light (lux) readings.

**Tip:** Ground the LED pin on the Adafruit board (connect to Pin 9) to disable the bright onboard LED.

### ambient powersave

Using the same sensor, set a light threshold and duration in the web UI. If ambient light stays below the threshold for the configured duration, the display powers off. The scheduler takes priority over the sensor during off hours.

## power on/off

Photoframe listens on GPIO 26 (configurable) for power control. Connect a momentary switch between pin 37 (GPIO 26) and pin 39 (GND) for graceful shutdown and power on.

## FAQ

### How do I get SSH access?

Place a file called `ssh` on the boot partition. Login with the default Raspberry Pi OS credentials. Avoid modifying files in `/root/photoframe/` directly, as this will prevent automatic updates via `update.sh`.

### Are there logs?

Logs are in `/var/log/syslog` (search for `frame` or `photoframe` entries). For verbose debug output:

```bash
service frame stop
/root/photoframe/frame.py --debug
```

### How do I test on a desktop?

Run `frame.py` with `--emulate` to run without RPi hardware.

### How do I build my own SD card image?

Check out the `photoframe` branch on https://github.com/dev-brewery/pi-gen for the pi-gen configuration used to build release images.

### USB sticks not recognized?

Install exFAT support: `sudo apt install exfat-fuse exfat-utils`

### How does "Refresh keywords" work?

Photo lists refresh when: (1) all photos have been shown, (2) "Forget Memory" is pressed in the web UI, or (3) the configured refresh interval expires. Set to 0 to disable timed refresh.

### What about photoframe.sensenet.nu?

This service handles OAuth redirect for Google Photos authorization behind firewalls. Since Google Photos is now deprecated, this is only relevant for legacy setups. See `extras/` if you want to self-host.

## license

[GNU General Public License v2.0](LICENSE)

Originally created by [mrworf](https://github.com/mrworf). Community maintained by [dev-brewery](https://github.com/dev-brewery).
