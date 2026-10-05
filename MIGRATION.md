# Migrating to dev-brewery/photoframe

This guide covers migrating from the original [mrworf/photoframe](https://github.com/mrworf/photoframe) to this community-maintained fork.

## What's changing?

- **Python 2 to Python 3** - new system packages required
- **New photo service: Immich** - self-hosted alternative to Google Photos
- **Google Photos deprecated** - Google removed the API ([details](GOOGLE_PHOTOS.md))
- **Display detection without tvservice** - where `tvservice` is missing, the display size is read from the framebuffer
- **Picasa removed** - the service was already non-functional

Your existing configuration (`/root/photoframe_config/`) is preserved during migration.

## Scenario A: Existing git-based install

If you installed photoframe by cloning the repo to `/root/photoframe`, you can use the migration script or do the same steps by hand.

The migration needs Raspberry Pi OS Bullseye or later, the same releases the install script supports. Older releases such as Buster and Stretch lack packages the fork installs or the Python version it needs (3.8 or later); on those, flash the current image instead (Scenario B). The script checks this and stops before changing anything.

### With the migration script

```bash
sudo su -
wget -O /root/migrate-from-mrworf.sh https://raw.githubusercontent.com/dev-brewery/photoframe/3.0.0/migrate-from-mrworf.sh
bash /root/migrate-from-mrworf.sh
```

The script:

1. Stops `frame.service` if it is running
2. Saves `/root/photoframe_config` as `/root/photoframe_config.backup.<date-time>.tar.gz`
3. Points the `origin` remote at this fork and checks out the `3.0.0` release branch
4. Installs the system and Python packages the fork needs
5. Installs the service file and starts the service

It can be run again without harm. If photoframe is not in `/root/photoframe`, set `REPO_DIR`, for example `REPO_DIR=/home/pi/photoframe bash /root/migrate-from-mrworf.sh`.

### By hand

```bash
# Run everything below as root
sudo su -

# 1. Stop the service
systemctl stop frame.service

# 2. Back up your configuration
cp -r /root/photoframe_config /root/photoframe_config.bak

# 3. Switch to the dev-brewery fork
cd /root/photoframe
git remote set-url origin https://github.com/dev-brewery/photoframe.git
git fetch origin
git checkout 3.0.0
git pull

# 4. Install the dependencies (the same list as install.sh; all from apt, no pip)
apt-get update
apt-get install -y python3 python3-smbus \
    python3-netifaces python3-flask python3-requests \
    python3-oauthlib python3-requests-oauthlib python3-flask-httpauth \
    imagemagick fbset git bc libjpeg-turbo-progs libheif-examples openssh-server

# 5. Update the service file
cp frame.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable frame.service

# 6. Restart
systemctl start frame.service
```

Verify via the web UI at `http://<your-pi-ip>:7777`.

## Scenario B: Existing SD card image install

mrworf's pre-built SD card images (2018 and 2019) are Raspbian Stretch, which the migration does not support (see Scenario A). Download the latest image from the [releases page](https://github.com/dev-brewery/photoframe/releases) and flash it to a new SD card. Your configuration from the old install will need to be set up again.

If you have since upgraded that system to a release Scenario A supports, you can follow Scenario A instead.

## Scenario C: Fresh install (no existing photoframe)

Use the install script on a clean Raspberry Pi OS (Bullseye, Bookworm or Trixie, 32-bit or 64-bit):

```bash
sudo apt-get update -y && sudo apt upgrade -y
sudo apt install -y git
sudo su -
git clone https://github.com/dev-brewery/photoframe.git /root/photoframe
cd /root/photoframe
./install.sh
systemctl start frame.service
```

The web UI will be available at `http://<your-pi-ip>:7777`.

## Setting up Immich (recommended)

After migration, add your Immich server as a photo source:

1. Open the web UI
2. Select **Immich** from the service dropdown
3. Click **Add photo service**
4. Upload a JSON config file:
   ```json
   {
     "server_url": "http://your-immich-server:2283",
     "api_key": "your-api-key"
   }
   ```
5. Add album names as keywords

See [README-Immich.md](README-Immich.md) for detailed setup and troubleshooting.

## Automatic updates

The fork uses the same `update.sh` auto-update mechanism. It follows the branch your install is on: after the migration above that is `3.0.0`, so the frame receives whatever is published to that branch. If you had a cron job for updates, it will continue to work after changing the git remote. If not, add one:

```bash
echo "15 3 * * * root /root/photoframe/update.sh" >> /etc/crontab
```

## Troubleshooting

### Service won't start after migration

Check the log:
```bash
journalctl -u frame.service -n 50
```

Common causes:
- Missing Python 3 packages (re-run step 4)
- Old `.pyc` bytecode files: `find /root/photoframe -name "*.pyc" -delete && find /root/photoframe -name "__pycache__" -exec rm -rf {} +`

### Display issues after migration

photoframe detects the display when it starts, and again when the Resolution setting is changed. If you have issues:
```bash
service frame stop
/root/photoframe/frame.py --debug
```

Look for lines mentioning the display or the framebuffer (in either case) in the output. How the size is found:

- If the `tvservice` command is installed, photoframe asks `tvservice` for the saved display mode. If `tvservice` does not report that mode, or fails, photoframe stops drawing to the display (the screen keeps whatever it last showed) and logs "Unable to find a valid display mode, will default to 1280x720".
- Otherwise it reads the size of the framebuffer (`/dev/fb0`) with `fbset`, and ignores the Resolution setting. If that fails, for example because `fbset` is not installed or `/dev/fb0` cannot be opened, it uses 800x480 and logs "Framebuffer detection failed, using safe default display configuration". If `fbset` is missing, install it with `apt-get install -y fbset`.
- With a custom display driver selected, it uses 1280x720: always without `tvservice`, and with `tvservice` when `tvservice` reports the driver's mode.

### Configuration not preserved

If settings are missing, restore them from the backup.

After the migration script (it saves `/root/photoframe_config.backup.<date-time>.tar.gz`):
```bash
tar -xzf /root/photoframe_config.backup.<date-time>.tar.gz -C /root
systemctl restart frame.service
```

After the by-hand steps (step 2 saves `/root/photoframe_config.bak`):
```bash
cp -r /root/photoframe_config.bak/* /root/photoframe_config/
systemctl restart frame.service
```
