# Migrating to dev-brewery/photoframe

This guide covers migrating from the original [mrworf/photoframe](https://github.com/mrworf/photoframe) to this community-maintained fork.

## What's changing?

- **Python 2 to Python 3** - new system packages required
- **New photo service: Immich** - self-hosted alternative to Google Photos
- **Google Photos deprecated** - Google removed the API ([details](GOOGLE_PHOTOS.md))
- **Modern display detection** - tvservice replaced with KMS/DRM + fallback chain
- **Picasa removed** - the service was already non-functional

Your existing configuration (`/root/photoframe_config/`) is preserved during migration.

## Scenario A: Existing git-based install

If you installed photoframe by cloning the repo to `/root/photoframe`:

```bash
# 1. Stop the service
sudo systemctl stop frame.service

# 2. Back up your configuration
cp -r /root/photoframe_config /root/photoframe_config.bak

# 3. Switch to the dev-brewery fork
cd /root/photoframe
git remote set-url origin https://github.com/dev-brewery/photoframe.git
git fetch origin
git checkout master
git pull

# 4. Install Python 3 dependencies
apt-get update
apt-get install -y python3 python3-pip python3-netifaces python3-flask python3-requests
pip3 install -r requirements.txt

# 5. Optional: HEIC/HEIF image support (for Apple photos)
apt-get install -y libheif-examples

# 6. Update the service file
cp frame.service /etc/systemd/system/
systemctl daemon-reload

# 7. Restart
systemctl start frame.service
```

Verify via the web UI at `http://<your-pi-ip>:7777`.

## Scenario B: Existing SD card image install

If you used one of mrworf's pre-built SD card images, follow the same steps as Scenario A. The SD card images used Python 2 system packages, so you will need to install the Python 3 packages listed in step 4.

If you prefer a fresh start, download the latest image from the [releases page](https://github.com/dev-brewery/photoframe/releases) and flash it to a new SD card. Your configuration from the old install will need to be set up again.

## Scenario C: Fresh install (no existing photoframe)

Use the install script on a clean Raspberry Pi OS (Bookworm or Bullseye, 32-bit or 64-bit):

```bash
sudo su -
git clone https://github.com/dev-brewery/photoframe.git /root/photoframe
cd /root/photoframe
chmod +x install.sh
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

The fork uses the same `update.sh` auto-update mechanism. If you had a cron job for updates, it will continue to work after changing the git remote. If not, add one:

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

The new display module auto-detects the best method. If you have issues:
```bash
service frame stop
/root/photoframe/frame.py --debug
```

Look for `display` entries in the output. The detection order is: KMS/DRM, xrandr, fbset, tvservice.

### Configuration not preserved

If settings are missing, restore from backup:
```bash
cp -r /root/photoframe_config.bak/* /root/photoframe_config/
systemctl restart frame.service
```
