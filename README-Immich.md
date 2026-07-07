# Immich Integration for PhotoFrame

This integration enables PhotoFrame to display photos from your personal Immich photo server, providing a self-hosted alternative to cloud-based photo services.

## What is Immich?

[Immich](https://immich.app/) is a self-hosted photo and video backup solution, similar to Google Photos but running on your own server. This integration allows PhotoFrame to connect to your Immich server and display your photos.

## Features

- **Direct Server Connection**: Connect PhotoFrame directly to your Immich server using API authentication
- **Album-Based Display**: Select specific albums to display as keywords
- **Immich v2/v3 Support**: Automatically detects the Immich server API version and uses the compatible album/photo retrieval path
- **Self-Hosted Privacy**: Keep your photos on your own server - no cloud services required
- **Web-Based Configuration**: Easy setup through PhotoFrame's web interface

## Setup Instructions

### Step 1: Get Your Immich API Key

1. Log into your Immich web interface
2. Go to **Account Settings** → **API Keys**
3. Click **New API Key**
4. Give it a name (e.g., "PhotoFrame")
5. Copy the generated API key

### Step 2: Configure PhotoFrame

1. Open PhotoFrame's web interface (usually `http://your-pi-ip:7777`)
2. Log in with your credentials (default: `photoframe` / `password`)
3. Click **Services** in the navigation
4. Click **Add Service** and select **Immich**
5. Upload a JSON configuration file or create one with this format:

```json
{
  "server_url": "https://your-immich-server.com",
  "api_key": "your-immich-api-key-here"
}
```

**Important Configuration Notes:**
- `server_url`: The full URL to your Immich server (include `https://` or `http://`)
- `api_key`: The API key you generated in Step 1
- **No trailing slashes** in the server URL
- Ensure your PhotoFrame can reach your Immich server (network connectivity)
- No API version setting is needed. PhotoFrame detects Immich v2 or v3 automatically.

### Step 3: Add Keywords (Albums)

1. After configuration, the service will move to **NEED_KEYWORDS** state
2. Click **Keywords** next to your Immich service
3. Add album names as keywords (case-sensitive)
4. The service will fetch photos from these albums

### Common Configuration Examples

**Local server with port:**
```json
{
  "server_url": "http://192.168.1.100:2283",
  "api_key": "your-api-key"
}
```

**HTTPS with custom domain:**
```json
{
  "server_url": "https://photos.yourdomain.com",
  "api_key": "your-api-key"
}
```

## Troubleshooting

### Service Shows "CONFIG" State
- Verify your JSON file has the correct format
- Check that `server_url` and `api_key` are properly quoted strings
- Ensure there are no extra commas or syntax errors

### Service Shows "Error" State
- Verify PhotoFrame can reach your Immich server (try the URL in a browser)
- Check that your API key is still valid in Immich settings
- Ensure the server URL is correct (no trailing slashes)
- Check PhotoFrame's debug logs for detailed error messages

### No Photos Displayed
- Verify the album names you added as keywords exist in Immich
- Check that the albums contain photos
- Ensure your API key has permission to access those albums
- Album names are case-sensitive
- If this started immediately after an Immich upgrade, restart PhotoFrame or clear memory/cache so the service re-detects the Immich API version and refreshes album indexes

### Network Issues
- If using HTTPS, ensure SSL certificates are valid
- Check firewall settings on both PhotoFrame and Immich server
- Verify DNS resolution if using domain names

## Current Limitations

- **Album names must match exactly** (case-sensitive)
- **No automatic album discovery** - you must specify album names as keywords
- **No video support** - only displays images from albums

## Security Notes

- Store your API key securely - treat it like a password
- Use HTTPS for your Immich server when possible
- Consider creating a dedicated API key specifically for PhotoFrame
- Regularly rotate API keys for security

## Technical Details

The Immich integration:
- Uses Immich's REST API for authentication and photo retrieval
- Supports Immich v2 and v3 API layouts through lightweight runtime detection
- Follows PhotoFrame's standard service pattern (`CONFIG` → `NEED_KEYWORDS` → `READY`)
- Integrates with PhotoFrame's existing caching and display pipeline
- Supports multiple Immich servers (add multiple services)
- Avoids generated API clients and heavy dependencies so the integration remains suitable for Raspberry Pi Zero W devices

For developers: The implementation is in `services/svc_immich.py` and uses the `needImmichConfig=True` flag to enable special configuration handling through the `/service/{id}/immichconfig` endpoint.
