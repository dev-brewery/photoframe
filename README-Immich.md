# Immich Integration for PhotoFrame

This integration enables PhotoFrame to display photos from your personal Immich photo server, providing a self-hosted alternative to cloud-based photo services.

## What is Immich?

[Immich](https://immich.app/) is a self-hosted photo and video backup solution, similar to Google Photos but running on your own server. This integration allows PhotoFrame to connect to your Immich server and display your photos.

## Supported Immich versions

photoframe 3.0.0 supports Immich v2.x servers. Immich v3 is not supported in this release; support is planned for photoframe 3.1.

## Features

- **Direct Server Connection**: Connect PhotoFrame directly to your Immich server using API authentication
- **Album-Based Display**: Select specific albums to display as keywords
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
2. If it asks for a login, use your web UI credentials (the SD card image's default is `photoframe` / `password`; see [web UI login](README.md#web-ui-login))
3. At the bottom of the page, select **Immich** in the dropdown and click **Add photo provider**
4. Give the service a name when asked
5. Give it your server details in one of two ways: click **Enter Credentials** and fill in the server URL and API key, or click **Upload Config** and choose a JSON file in this format:

```json
{
  "server_url": "https://your-immich-server.com",
  "api_key": "your-immich-api-key-here"
}
```

**Important Configuration Notes:**
- `server_url`: The full URL to your Immich server (include `https://` or `http://`)
- `api_key`: The API key you generated in Step 1
- A single trailing slash on the server URL is removed for you
- Ensure your PhotoFrame can reach your Immich server (network connectivity)

### Step 3: Add Keywords (Albums)

1. Once the configuration is accepted, the Immich service shows a text box with **Help**, **Browse** and **Add** buttons
2. Click **Browse** to pick from the albums on your server, or type an album name into the text box
3. Click **Add**. The service will fetch photos from that album
4. Repeat for each album you want shown

An album name is matched exactly first. If there is no exact match, it is matched ignoring upper and lower case. An album can only be added once.

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
- Ensure the server URL is correct
- Check PhotoFrame's debug logs for detailed error messages

### No Photos Displayed
- Verify the album names you added as keywords exist in Immich
- Check that the albums contain photos
- Ensure your API key has permission to access those albums
- Use **Browse** to see the album names the server reports

### Network Issues
- If using HTTPS, ensure SSL certificates are valid
- Check firewall settings on both PhotoFrame and Immich server
- Verify DNS resolution if using domain names

## Current Limitations

- **No video support** - only displays images from albums

## Security Notes

- Store your API key securely - treat it like a password
- Use HTTPS for your Immich server when possible
- Consider creating a dedicated API key specifically for PhotoFrame
- Regularly rotate API keys for security

## Technical Details

The Immich integration:
- Uses Immich's REST API for authentication and photo retrieval
- Follows PhotoFrame's standard service pattern (`CONFIG` → `NEED_KEYWORDS` → `READY`)
- Integrates with PhotoFrame's existing caching and display pipeline
- Supports multiple Immich servers (add multiple services)

For developers: The implementation is in `services/svc_immich.py` and uses the `needImmichConfig=True` flag to enable special configuration handling through the `/service/{id}/immichconfig` endpoint.