# This file is part of photoframe (https://github.com/mrworf/photoframe).
#
# photoframe is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# photoframe is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with photoframe.  If not, see <http://www.gnu.org/licenses/>.
#
from services.base import BaseService
import os
import json
import logging
import time
import requests
import shutil

from modules.network import RequestResult, RequestNoNetwork, RequestTerminalError, RetryConfig
from modules.helper import helper


class Immich(BaseService):
    SERVICE_NAME = 'Immich'
    SERVICE_ID = 10
    MAX_ITEMS = 8000

    def __init__(self, configDir, id, name):
        BaseService.__init__(self, configDir, id, name, needConfig=False, needOAuth=False, needImmichConfig=True)
        # First call always returns thumbnail?size=preview so the slideshow
        # starts visibly with a small/fast download. Subsequent calls escalate
        # via dimension + memory + policy heuristics in getContentUrl().
        self._settled = False

    # ------------------ Configuration ------------------

    def getConfigurationFields(self):
        return {
            'server_url': {
                'type': 'STR',
                'name': 'Server URL',
                'description': 'Full URL to your Immich server (e.g., https://immich.example.com)'
            },
            'api_key': {
                'type': 'PW',
                'name': 'API Key',
                'description': 'Immich API key for authentication. Generate this in Immich User Settings.'
            }
        }

    def validateImmichConfiguration(self, config):
        logging.info(f'Immich validateConfiguration called with config: {config}')
        if not config:
            return 'Configuration is required'
        if 'server_url' not in config or not config['server_url']:
            return 'Server URL is required'
        if 'api_key' not in config or not config['api_key']:
            return 'API Key is required'
        server_url = config['server_url'].strip()
        if not server_url.startswith(('http://', 'https://')):
            return 'Server URL must start with http:// or https://'
        if server_url.endswith('/'):
            config['server_url'] = server_url[:-1]
        logging.info('Immich configuration validated successfully')
        return True

    def helpKeywords(self):
        return 'Enter an Immich album name. Matching is case-insensitive; the resolved album name will be shown after adding.'

    def hasKeywordSourceUrl(self):
        return True

    def getExtras(self):
        result = BaseService.getExtras(self)
        if result is None:
            return {}
        return result

    def postSetup(self):
        extras = self.getExtras()
        if len(self.getKeywords()) == 0 and len(extras) > 0:
            logging.warning('Mismatch between keywords and extras info, corrected')
            self.setExtras({})

    def getKeywordSourceUrl(self, index):
        keys = self.getKeywords()
        if index < 0 or index >= len(keys):
            return f'Out of range, index = {index}'
        keyword = keys[index]
        extras = self.getExtras()
        if keyword not in extras:
            return 'http://your-immich-server/'
        return extras[keyword]['sourceUrl']

    def getKeywordDetails(self, index):
        keys = self.getKeywords()
        if index < 0 or index >= len(keys):
            return f'Out of range, index = {index}'
        keyword = keys[index]
        extras = self.getExtras()
        if keyword not in extras:
            return {
                'short': f'Album "{keyword}" not found in extras',
                'long': ['Album information missing', 'Try removing and re-adding this album']
            }
        album_info = extras[keyword]
        asset_count = album_info.get('assetCount', 0)
        created_at = album_info.get('createdAt', 'Unknown')
        description = album_info.get('description', 'No description')
        return {
            'short': f'Album "{keyword}" - {asset_count} assets',
            'long': [
                f'Album ID: {album_info.get("albumId", "Unknown")}',
                f'Assets: {asset_count}',
                f'Created: {created_at[:10] if created_at != "Unknown" else "Unknown"}',
                f'Description: {description if description else "No description"}',
                'Real photo retrieval now available'
            ]
        }

    def hasKeywordDetails(self):
        return True

    def removeKeywords(self, index):
        keys = self.getKeywords()
        if index < 0 or index >= len(keys):
            return
        keywords = keys[index].strip()
        filename = os.path.join(self.getStoragePath(), self.hashString(keywords) + '.json')
        if os.path.exists(filename):
            os.unlink(filename)
        if BaseService.removeKeywords(self, index):
            extras = self.getExtras()
            if keywords in extras:
                del extras[keywords]
                self.setExtras(extras)
            return True
        return False

    # ------------------ Album Discovery ------------------

    def getQueryForKeyword(self, keyword):
        result = None
        extras = self.getExtras()
        if extras is None:
            extras = {}
        if keyword in extras:
            result = {'albumId': extras[keyword]['albumId']}
        return result

    def discoverAlbums(self):
        config = self.getImmichConfiguration()
        if not config or 'server_url' not in config or 'api_key' not in config:
            return {'success': False, 'albums': [], 'error': 'Immich configuration not found'}

        server_url = config['server_url']
        api_key = config['api_key']
        albums_url = f"{server_url}/api/albums"
        headers = {'x-api-key': api_key, 'Accept': 'application/json'}

        try:
            logging.debug(f'Immich discoverAlbums: calling GET {albums_url}')
            retry_config = RetryConfig()
            response = None

            for attempt in range(retry_config.max_retries):
                try:
                    response = requests.get(albums_url, headers=headers, timeout=180)
                    if RetryConfig.is_terminal_code(response.status_code):
                        raise RequestTerminalError(f'Immich returned HTTP {response.status_code}', status_code=response.status_code)
                    if not RetryConfig.is_transient_code(response.status_code):
                        break  # Success or non-transient
                    delay = retry_config.get_delay(attempt)
                    logging.warning(f'Transient HTTP {response.status_code} from Immich, pausing {delay:.1f}s')
                    time.sleep(delay)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    delay = retry_config.get_delay(attempt)
                    if attempt + 1 < retry_config.max_retries:
                        logging.warning(f'Network error calling Immich: {type(e).__name__}, pausing {delay:.1f}s')
                        time.sleep(delay)
                    else:
                        raise RequestNoNetwork(f'Failed to connect to Immich server: {str(e)}')

            if response is None:
                raise RequestNoNetwork('No response from Immich server')

            # Log if we exhausted retries on transient errors
            if RetryConfig.is_transient_code(response.status_code):
                logging.warning(f'Immich albums API failed after {retry_config.max_retries} retries with HTTP {response.status_code}')

            if response.status_code == 200:
                albums_data = response.json()
                logging.info(f'Immich discoverAlbums: successfully retrieved {len(albums_data)} albums')
                return {'success': True, 'albums': albums_data, 'error': None}
            else:
                return {'success': False, 'albums': [], 'error': f'Server returned error {response.status_code}'}

        except RequestTerminalError as e:
            if e.status_code == 401:
                return {'success': False, 'albums': [], 'error': 'Authentication failed. Check your API key.'}
            elif e.status_code == 403:
                return {'success': False, 'albums': [], 'error': 'Access denied. Check API key permissions.'}
            elif e.status_code == 404:
                return {'success': False, 'albums': [], 'error': 'Immich server not found. Check server URL.'}
            return {'success': False, 'albums': [], 'error': str(e)}
        except RequestNoNetwork as e:
            return {'success': False, 'albums': [], 'error': f'Network error: {str(e)}'}
        except Exception as e:
            return {'success': False, 'albums': [], 'error': f'Unexpected error: {str(e)}'}

    # ------------------ Keywords / Album Lookup ------------------

    def validateKeywords(self, keywords):
        tst = BaseService.validateKeywords(self, keywords)
        if tst["error"] is not None:
            return tst

        if len(keywords) >= 2 and keywords[0] == '"' and keywords[-1] == '"':
            keywords = keywords[1:-1]
        keywords = keywords.strip()
        if not keywords:
            return {'error': 'Album name cannot be empty', 'keywords': keywords}

        discovery_result = self.discoverAlbums()
        if not discovery_result['success']:
            return {'error': f'Failed to connect to Immich server: {discovery_result["error"]}', 'keywords': keywords}

        albums = discovery_result['albums']
        if not albums:
            return {'error': 'No albums found on Immich server', 'keywords': keywords}

        # Try exact-case match first
        exact_matches = [a for a in albums if (a.get('albumName') or a.get('name', '')) == keywords]

        if len(exact_matches) == 1:
            matched_album = exact_matches[0]
            logging.debug(f'Album "{keywords}" matched exactly')
        elif len(exact_matches) > 1:
            matched_album = exact_matches[0]
            logging.warning(f'Multiple albums with exact name "{keywords}", using first match')
        else:
            # Fall back to case-insensitive match
            case_fold_matches = [a for a in albums if (a.get('albumName') or a.get('name', '')).lower() == keywords.lower()]

            if len(case_fold_matches) == 0:
                available_names = [a.get('albumName', a.get('name', 'Unknown')) for a in albums[:10]]
                available_list = ', '.join(available_names)
                if len(albums) > 10:
                    available_list += f', ... and {len(albums) - 10} more'
                return {'error': f'No album found matching "{keywords}" (case-insensitive). Available albums: {available_list}', 'keywords': keywords}

            if len(case_fold_matches) == 1:
                matched_album = case_fold_matches[0]
                actual_name = matched_album.get('albumName') or matched_album.get('name', '')
                logging.info(f'Album "{keywords}" matched via case-fold to "{actual_name}"')
            else:
                # Multiple case-fold matches - prefer one starting with same first char
                sorted_matches = sorted(
                    case_fold_matches,
                    key=lambda a: (
                        not (a.get('albumName') or a.get('name', '')).lower().startswith(keywords[:1].lower() if keywords else ''),
                        len(a.get('albumName') or a.get('name', ''))
                    )
                )
                matched_album = sorted_matches[0]
                actual_name = matched_album.get('albumName') or matched_album.get('name', '')
                other_names = [a.get('albumName', a.get('name', '')) for a in sorted_matches[1:3]]
                logging.warning(f'Multiple albums match "{keywords}" via case-fold. Using "{actual_name}". Other matches: {other_names}')

        # Check if this album ID is already added under a different keyword (case-variant duplicate)
        matched_album_id = matched_album.get('id')
        existing_extras = self.getExtras()
        for existing_kw, existing_info in existing_extras.items():
            if existing_info.get('albumId') == matched_album_id:
                return {'error': f'Album already added as "{existing_kw}"', 'keywords': keywords}

        config = self.getImmichConfiguration()
        server_url = config.get('server_url', '') if config else ''

        albumInfo = {
            'albumId': matched_album.get('id'),
            'sourceUrl': f'{server_url}/albums/{matched_album.get("id")}',
            'albumName': matched_album.get('albumName', matched_album.get('name', keywords)),
            'description': matched_album.get('description', ''),
            'assetCount': matched_album.get('assetCount', 0),
            'createdAt': matched_album.get('createdAt', ''),
            'updatedAt': matched_album.get('updatedAt', '')
        }

        # Return canonical album name (better UX: "summer 2023" becomes "Summer 2023")
        canonical_name = albumInfo['albumName']
        return {'error': None, 'keywords': canonical_name, 'extras': albumInfo}

    def addKeywords(self, keywords):
        result = BaseService.addKeywords(self, keywords)
        if result['error'] is None and result['extras'] is not None:
            k = result['keywords']
            extras = self.getExtras()
            extras[k] = result['extras']
            self.setExtras(extras)
        return result

    # ------------------ Image Retrieval ------------------

    def getImagesFor(self, keyword, rawReturn=False):
        """Get images for keyword from Immich album.

        The album endpoint returns full asset metadata - no need for individual asset calls.
        """
        logging.debug(f'Immich getImagesFor: keyword="{keyword}"')

        query = self.getQueryForKeyword(keyword)
        if query is None:
            logging.error(f'Unable to create query for keyword "{keyword}"')
            return []

        config = self.getImmichConfiguration()
        if not config or 'server_url' not in config or 'api_key' not in config:
            logging.error('Immich configuration not found')
            return []

        headers = {'x-api-key': config['api_key']}

        # Fetch album - this returns full asset metadata in one call
        album_url = f"{config['server_url']}/api/albums/{query['albumId']}"
        try:
            response = requests.get(album_url, headers=headers, timeout=30)
            if not response.ok:
                logging.warning(f'Immich API call failed with status {response.status_code}')
                return []

            album_data = response.json()
            assets = album_data.get('assets', [])
            if not assets:
                logging.warning(f'No assets found in album for keyword "{keyword}"')
                return []

            logging.info(f'Retrieved {len(assets)} assets from album "{keyword}"')

        except Exception as e:
            logging.error(f'Failed to get images for keyword "{keyword}": {e}')
            return []

        # Cache to JSON file
        filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
        try:
            with open(filename, 'w') as f:
                json.dump(assets, f)
        except Exception as e:
            logging.exception(f'Failed to save JSON cache file: {e}')

        if rawReturn:
            return assets

        return self.parseAlbumInfo(assets, keyword)

    def parseAlbumInfo(self, data, keyword):
        """Convert Immich assets to ImageHolder objects that BaseService can use"""
        logging.info(f'Parsing {len(data)} assets for keyword "{keyword}"')
        result = []

        supported_images = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/webp', 'image/tiff', 'image/tif', 'image/bmp',
            'image/heic', 'image/heif'
        }

        # Get config once outside the loop
        config = self.getImmichConfiguration()
        server_url = config.get('server_url', '') if config else ''

        for i, asset in enumerate(data):
            asset_id = asset.get('id')
            if not asset_id:
                logging.warning(f'Asset {i+1} missing ID, skipping')
                continue
            
            # Check if it's a video and skip
            asset_type = asset.get('type')
            if asset_type == 'VIDEO':
                logging.debug(f'Asset {i+1}: skipping video {asset_id}')
                continue
            
            # Get the actual mimeType (album endpoint returns 'originalMimeType')
            mime_type = asset.get('originalMimeType') or asset.get('mimeType')
            
            # If mimeType is missing, try to infer from filename
            if not mime_type:
                original_filename = (asset.get('originalFileName', '') or '').lower()
                if original_filename.endswith(('.jpg', '.jpeg')):
                    mime_type = 'image/jpeg'
                elif original_filename.endswith('.png'):
                    mime_type = 'image/png'
                elif original_filename.endswith('.gif'):
                    mime_type = 'image/gif'
                elif original_filename.endswith('.webp'):
                    mime_type = 'image/webp'
                elif original_filename.endswith(('.tiff', '.tif')):
                    mime_type = 'image/tiff'
                elif original_filename.endswith('.bmp'):
                    mime_type = 'image/bmp'
                elif original_filename.endswith(('.heic', '.heif')):
                    mime_type = 'image/heic'
                else:
                    mime_type = 'image/jpeg'
                    logging.debug(f'Asset {i+1}: defaulting to image/jpeg for {asset_id}')
            
            # Skip unsupported types
            if mime_type not in supported_images:
                logging.debug(f'Asset {i+1}: skipping unsupported type {mime_type}')
                continue
            
            # Create ImageHolder with all required fields
            image = self.createImageHolder()
            
            # Set the ID - used for tracking
            image.setId(asset_id)
            
            # Set the mimetype - BaseService filters by this
            image.setMimetype(mime_type)
            
            # Set the URL - use preview endpoint by default to avoid OOM on
            # memory-constrained devices. getContentUrl() upgrades to original
            # or fullsize when display hints indicate it's safe.
            if server_url:
                image.url = f"{server_url}/api/assets/{asset_id}/thumbnail?size=preview"
            
            # Set filename if available
            original_filename = asset.get('originalFileName')
            if original_filename:
                image.setFilename(original_filename)
            
            # Set dimensions - BaseService uses this for orientation checks
            exif_info = asset.get('exifInfo', {}) or {}
            width = exif_info.get('exifImageWidth')
            height = exif_info.get('exifImageHeight')
            
            # If EXIF dimensions aren't available, check asset level
            if not width or not height:
                width = asset.get('width')
                height = asset.get('height')
            
            if width and height:
                try:
                    image.setDimensions(int(width), int(height))
                    # Also set the dimensions dict that BaseService expects
                    image.dimensions = {'width': int(width), 'height': int(height)}
                except (ValueError, TypeError):
                    logging.debug(f'Asset {i+1}: invalid dimensions for {asset_id}')
            
            # Enable caching
            image.allowCache(True)
            
            # Set source URL for UI display
            if server_url:
                image.source = f"{server_url}/photos/{asset_id}"
            
            result.append(image)
            logging.debug(f'Added asset {asset_id} ({mime_type}) with dimensions {width}x{height}')
        
        logging.info(f'Parsed {len(result)} supported images from {len(data)} total assets')
        return result

    # ImageMagick policy limits (from /etc/ImageMagick-6/policy.xml on Bookworm)
    IMAGEMAGICK_MAX_DIMENSION = 16384  # 16KP width/height limit
    IMAGEMAGICK_MAX_AREA = 128_000_000  # 128MP area limit

    def getContentUrl(self, image, hints):
        config = self.getImmichConfiguration()
        if not config or 'server_url' not in config:
            return None
        asset_id = image.id
        if not asset_id:
            return None

        endpoint = 'thumbnail?size=preview'

        if self._settled and image.dimensions:
            width = image.dimensions.get('width', 0)
            height = image.dimensions.get('height', 0)
            if width > 0 and height > 0 and self._canProcessImage(width, height):
                disp = hints.get('display', {}) if hints else {}
                max_display = max(disp.get('width', 0), disp.get('height', 0))
                if max_display > 1920:
                    endpoint = 'original'
                else:
                    endpoint = 'thumbnail?size=fullsize'
        self._settled = True

        return f"{config['server_url']}/api/assets/{asset_id}/{endpoint}"

    def _canProcessImage(self, width, height):
        """Check available memory and ImageMagick policy limits."""
        if width > self.IMAGEMAGICK_MAX_DIMENSION or height > self.IMAGEMAGICK_MAX_DIMENSION:
            return False
        if width * height > self.IMAGEMAGICK_MAX_AREA:
            return False
        estimated_mb = (width * height * 20) / (1024 * 1024)
        safety_buffer_mb = 200
        available_mb = self._getAvailableMemoryMB()
        return available_mb >= estimated_mb + safety_buffer_mb

    def _getAvailableMemoryMB(self):
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):
                        return int(line.split()[1]) / 1024
        except Exception:
            return 0
        return 0

    def requestUrl(self, url, destination=None, params=None, data=None, usePost=False):
        """Override to add Immich authentication headers"""
        config = self.getImmichConfiguration()
        
        # Check if this is an Immich URL that needs authentication
        if config and 'server_url' in config and url and url.startswith(config['server_url']):
            headers = {'x-api-key': config['api_key']}
            retry_config = RetryConfig()
            r = None

            for attempt in range(retry_config.max_retries):
                try:
                    if usePost:
                        r = requests.post(url, params=params, json=data, headers=headers, timeout=180)
                    else:
                        r = requests.get(url, params=params, headers=headers, timeout=180, stream=True)

                    # Terminal errors - don't retry, raise immediately
                    if RetryConfig.is_terminal_code(r.status_code):
                        logging.error(f'Terminal HTTP {r.status_code} from Immich, not retrying')
                        raise RequestTerminalError(f'Immich returned HTTP {r.status_code}', status_code=r.status_code)

                    # Transient errors - retry with backoff
                    if RetryConfig.is_transient_code(r.status_code):
                        delay = retry_config.get_delay(attempt)
                        logging.warning(f'Transient HTTP {r.status_code} from Immich, pausing {delay:.1f}s')
                        time.sleep(delay)
                        continue

                    # Success
                    break

                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    delay = retry_config.get_delay(attempt)
                    if attempt + 1 < retry_config.max_retries:
                        logging.warning(f'Network error from Immich: {type(e).__name__}, pausing {delay:.1f}s')
                        time.sleep(delay)
                    else:
                        logging.error(f'Network unavailable after {retry_config.max_retries} attempts: {e}')
                        return RequestResult().setResult(RequestResult.NO_NETWORK)

            if r is None:
                logging.error('No response from Immich server after retries')
                return RequestResult().setResult(RequestResult.NO_NETWORK)

            result = RequestResult()
            result.setHTTPCode(r.status_code).setHeaders(r.headers).setResult(RequestResult.SUCCESS)

            if r.status_code != 200:
                logging.error(f'Immich returned status {r.status_code} for {url}')
                result.setResult(RequestResult.UNKNOWN)
                return result
            
            if destination is None:
                result.setContent(r.content)
            else:
                with open(destination, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                result.setFilename(destination)
                logging.info(f'Downloaded Immich asset to {destination}')
            
            return result
        
        # Not an Immich URL, use parent's implementation
        return BaseService.requestUrl(self, url, destination, params, data, usePost)

    # ------------------ Misc ------------------

    def freshnessImagesFor(self, keyword):
        filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
        if not os.path.exists(filename):
            return 0
        return (time.time() - os.stat(filename).st_mtime) / 3600

    def clearImagesFor(self, keyword):
        filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
        if os.path.exists(filename):
            os.unlink(filename)
        logging.info(f'Cleared image information for {keyword}')

    def selectRandomImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize):
        result = BaseService.selectRandomImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize)
        if result is not None:
            return result
        return BaseService.createImageHolder(self).setError('Immich service ready.\nReal photo retrieval available for configured albums.')
    
    def selectNextImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize):
        result = BaseService.selectNextImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize)
        if result is not None:
            return result
        return BaseService.createImageHolder(self).setError('Immich service ready.\nReal photo retrieval available for configured albums.')

    def getMessages(self):
        msgs = BaseService.getMessages(self)
        if self.hasConfiguration():
            msgs.append({
                'level': 'INFO',
                'message': 'Immich service configured and ready. Photo retrieval available for added albums.',
                'link': None
            })
        return msgs

    def explainState(self):
        state = self.updateState()
        if state == BaseService.STATE_DO_CONFIG:
            return 'Please configure your Immich server URL and API key to connect to your Immich instance.'
        elif state == BaseService.STATE_NEED_KEYWORDS:
            return 'Add album names as keywords to specify which Immich albums to display photos from.'
        elif state == BaseService.STATE_NO_IMAGES:
            return 'Immich service configured. Add album keywords to display photos from your Immich albums.'
        elif state == BaseService.STATE_READY:
            return 'Immich service ready. Real photo retrieval available from configured albums.'
        return None