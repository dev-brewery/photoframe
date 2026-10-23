# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 3.0.1 | Yes |
| 3.0.0 | No. It shows no photos from Immich v3 servers. Switch to 3.0.1. |
| mrworf/photoframe 2.x and older | No |

Frames follow the release branch they were installed from and do not move to a new release on their own. To move a frame to 3.0.1:

```bash
sudo git -C /root/photoframe fetch origin
sudo git -C /root/photoframe switch 3.0.1
sudo systemctl restart frame.service
```

## Immich servers

Immich publishes security fixes for v3 only. Keep your Immich server on a current v3 release, 3.3.5 or later. See [Immich v3.3.5](https://github.com/immich-app/immich/releases/tag/v3.3.5) and [GHSA-72rm-x7xr-v679](https://github.com/immich-app/immich/security/advisories/GHSA-72rm-x7xr-v679). photoframe supports Immich v3 from 3.0.1.

## Reporting a vulnerability

Report it privately with **Report a vulnerability** on this repository's [Security tab](https://github.com/dev-brewery/photoframe/security). Do not open a public issue.
