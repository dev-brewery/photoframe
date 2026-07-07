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
import json
import logging
import os
import time

import requests

from modules.network import RequestResult, RequestNoNetwork


class ImmichApiError(Exception):
    pass


class ImmichAuthError(ImmichApiError):
    pass


class ImmichSchemaError(ImmichApiError):
    pass


class ImmichApiBase:
    API_VERSION = 0

    def __init__(self, config, api_prefix='/api'):
        self.server_url = config['server_url'].rstrip('/')
        self.api_key = config['api_key']
        self.api_prefix = api_prefix or ''
        self.api_base = f'{self.server_url}{self.api_prefix}'

    def _headers(self):
        return {'x-api-key': self.api_key, 'Accept': 'application/json'}

    def _request(self, method, path, params=None, data=None, timeout=30, stream=False):
        url = f'{self.api_base}{path}'
        last_error = None

        for attempt in range(5):
            try:
                response = requests.request(
                    method,
                    url,
                    params=params,
                    json=data,
                    headers=self._headers(),
                    timeout=timeout,
                    stream=stream
                )
                break
            except requests.exceptions.RequestException as e:
                last_error = e
                logging.exception(f'Issues calling Immich API, attempt {attempt + 1}')
                if attempt == 4:
                    raise RequestNoNetwork(f'Failed to connect to Immich server: {e}')

            time.sleep(attempt * 10)
            logging.warning(f'Retrying Immich API call, attempt #{attempt + 2}')
        else:
            raise RequestNoNetwork(f'Failed to connect to Immich server: {last_error}')

        if response.status_code in (401, 403):
            raise ImmichAuthError('Authentication failed. Check your Immich API key.')
        if response.status_code == 404:
            raise ImmichSchemaError(f'Immich endpoint was not found: {path}')
        if response.status_code == 429 or response.status_code >= 500:
            raise RequestNoNetwork(f'Immich server returned HTTP {response.status_code}')
        if response.status_code < 200 or response.status_code >= 300:
            raise ImmichApiError(f'Immich server returned HTTP {response.status_code}')

        return response

    def _request_json(self, method, path, params=None, data=None, timeout=30):
        response = self._request(method, path, params=params, data=data, timeout=timeout)
        try:
            return response.json()
        except ValueError as e:
            raise ImmichSchemaError(f'Immich returned non-JSON response for {path}: {e}')

    def list_albums(self):
        albums = self._request_json('GET', '/albums', timeout=180)
        if not isinstance(albums, list):
            raise ImmichSchemaError('Immich album list response was not an array')
        return albums

    def get_album_assets(self, album_id):
        raise NotImplementedError()

    def asset_url(self, asset_id, endpoint):
        return f'{self.api_base}/assets/{asset_id}/{endpoint}'

    def photo_source_url(self, asset_id):
        return f'{self.server_url}/photos/{asset_id}'

    def album_source_url(self, album_id):
        return f'{self.server_url}/albums/{album_id}'


class ImmichV2Api(ImmichApiBase):
    API_VERSION = 2

    def get_album_assets(self, album_id):
        album = self._request_json('GET', f'/albums/{album_id}')
        if not isinstance(album, dict):
            raise ImmichSchemaError('Immich album response was not an object')
        if 'assets' not in album:
            raise ImmichSchemaError('Immich v2 album response did not include assets')
        assets = album.get('assets') or []
        if not isinstance(assets, list):
            raise ImmichSchemaError('Immich album assets response was not an array')
        return assets


class ImmichV3Api(ImmichApiBase):
    API_VERSION = 3

    def get_album_assets(self, album_id):
        data = {
            'albumIds': [album_id],
            'type': 'IMAGE',
            'withExif': True
        }
        assets = self._request_json('POST', '/search/large-assets', data=data)
        if isinstance(assets, dict) and isinstance(assets.get('items'), list):
            assets = assets['items']
        if not isinstance(assets, list):
            raise ImmichSchemaError('Immich v3 asset search response was not an array')
        return assets


def _parse_immich_version(data):
    if not isinstance(data, dict):
        return None

    try:
        major = int(data['major'])
        minor = int(data['minor'])
        patch = int(data['patch'])
    except (KeyError, TypeError, ValueError):
        return None

    result = {'major': major, 'minor': minor, 'patch': patch}
    if data.get('prerelease') is not None:
        result['prerelease'] = data.get('prerelease')
    return result


def detect_immich_api(config):
    server_url = config['server_url'].rstrip('/')
    headers = {'x-api-key': config['api_key'], 'Accept': 'application/json'}

    for api_prefix in ('/api', ''):
        url = f'{server_url}{api_prefix}/server/version'
        try:
            response = requests.request('GET', url, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            raise RequestNoNetwork(f'Failed to connect to Immich server: {e}')

        if response.status_code in (401, 403):
            raise ImmichAuthError('Authentication failed. Check your Immich API key.')
        if response.status_code != 200:
            continue

        try:
            version_info = _parse_immich_version(response.json())
        except ValueError:
            version_info = None

        if version_info is None:
            continue

        api_version = 3 if version_info['major'] >= 3 else 2
        version_info.update({
            'api_version': api_version,
            'api_prefix': api_prefix,
            'server_url': server_url
        })
        return version_info

    raise ImmichSchemaError('Unable to detect a supported Immich API version')


class Immich(BaseService):
    SERVICE_NAME = 'Immich'
    SERVICE_ID = 10
    MAX_ITEMS = 8000
    API_INFO_STATE_KEY = '_IMMICH_API_INFO'

    def __init__(self, configDir, id, name):
        BaseService.__init__(self, configDir, id, name, needConfig=False, needOAuth=False, needImmichConfig=True)

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
        config['server_url'] = server_url.rstrip('/')
        logging.info('Immich configuration validated successfully')
        return True

    def setImmichConfiguration(self, config):
        self._STATE.pop(self.API_INFO_STATE_KEY, None)
        self._IMAGE_CACHE.clear()
        BaseService.setImmichConfiguration(self, config)

    def _apiInfoMatchesConfig(self, api_info, config):
        if not api_info or not config:
            return False
        return api_info.get('server_url') == config.get('server_url', '').rstrip('/')

    def _createApiFromInfo(self, config, api_info):
        api_prefix = api_info.get('api_prefix', '/api')
        if api_info.get('api_version') == 3 or api_info.get('major', 0) >= 3:
            return ImmichV3Api(config, api_prefix)
        return ImmichV2Api(config, api_prefix)

    def _clearApiInfo(self):
        self._STATE.pop(self.API_INFO_STATE_KEY, None)
        self.saveState()

    def _getImmichApi(self, forceDetect=False):
        config = self.getImmichConfiguration()
        if not config or 'server_url' not in config or 'api_key' not in config:
            raise ImmichApiError('Immich configuration not found')

        api_info = self._STATE.get(self.API_INFO_STATE_KEY)
        if not forceDetect and self._apiInfoMatchesConfig(api_info, config):
            return self._createApiFromInfo(config, api_info)

        api_info = detect_immich_api(config)
        self._STATE[self.API_INFO_STATE_KEY] = api_info
        self.saveState()
        logging.info(
            f'Detected Immich API v{api_info["api_version"]} '
            f'from server version {api_info["major"]}.{api_info["minor"]}.{api_info["patch"]}'
        )
        return self._createApiFromInfo(config, api_info)

    def _callWithApiRetry(self, callback):
        api = self._getImmichApi()
        try:
            return callback(api)
        except ImmichSchemaError:
            logging.warning('Immich API shape changed or cached API version is stale, re-detecting')
            self._clearApiInfo()
            api = self._getImmichApi(forceDetect=True)
            return callback(api)

    def _getApiBaseUrl(self):
        config = self.getImmichConfiguration()
        if not config or 'server_url' not in config:
            return None
        api_info = self._STATE.get(self.API_INFO_STATE_KEY) or {}
        api_prefix = api_info.get('api_prefix', '/api')
        return f'{config["server_url"].rstrip("/")}{api_prefix}'

    def helpKeywords(self):
        return 'Each entry represents the name of an Immich album. Enter the exact album name as it appears in your Immich library.'

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

    def _albumName(self, album, default='Unknown'):
        return album.get('albumName') or album.get('name') or default

    def discoverAlbums(self):
        if not self.hasImmichConfiguration():
            return {'success': False, 'albums': [], 'error': 'Immich configuration not found'}

        try:
            albums_data = self._callWithApiRetry(lambda api: api.list_albums())
            logging.info(f'Immich discoverAlbums: successfully retrieved {len(albums_data)} albums')
            return {'success': True, 'albums': albums_data, 'error': None}
        except RequestNoNetwork as e:
            return {'success': False, 'albums': [], 'error': f'Network error: {str(e)}'}
        except ImmichAuthError as e:
            return {'success': False, 'albums': [], 'error': str(e)}
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

        matching_albums = [a for a in albums if self._albumName(a, '').lower() == keywords.lower()]
        if len(matching_albums) == 0:
            available_names = [self._albumName(a) for a in albums[:10]]
            available_list = ', '.join(available_names)
            if len(albums) > 10:
                available_list += f', ... and {len(albums) - 10} more'
            return {'error': f'No album found with name "{keywords}". Available albums: {available_list}', 'keywords': keywords}

        matched_album = matching_albums[0]
        api = self._getImmichApi()

        albumInfo = {
            'albumId': matched_album.get('id'),
            'sourceUrl': api.album_source_url(matched_album.get('id')),
            'albumName': self._albumName(matched_album, keywords),
            'description': matched_album.get('description', ''),
            'assetCount': matched_album.get('assetCount', 0),
            'createdAt': matched_album.get('createdAt', ''),
            'updatedAt': matched_album.get('updatedAt', '')
        }

        return {'error': None, 'keywords': keywords, 'extras': albumInfo}

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
        """Get images for keyword from Immich album."""
        logging.debug(f'Immich getImagesFor: keyword="{keyword}"')

        query = self.getQueryForKeyword(keyword)
        if query is None:
            logging.error(f'Unable to create query for keyword "{keyword}"')
            return []

        try:
            assets = self._callWithApiRetry(lambda api: api.get_album_assets(query['albumId']))
        except RequestNoNetwork as e:
            logging.error(f'Temporary Immich network failure for keyword "{keyword}": {e}')
            return None
        except ImmichAuthError as e:
            logging.error(f'Immich authentication failed for keyword "{keyword}": {e}')
            return [self.createImageHolder().setError(str(e))]
        except ImmichApiError as e:
            logging.error(f'Immich API failed for keyword "{keyword}": {e}')
            return [self.createImageHolder().setError(f'Immich API failed: {e}')]
        except Exception as e:
            logging.exception(f'Failed to get images for keyword "{keyword}"')
            return [self.createImageHolder().setError(f'Failed to get Immich images: {e}')]

        if not assets:
            logging.warning(f'No assets found in album for keyword "{keyword}"')
            return []

        logging.info(f'Retrieved {len(assets)} assets from album "{keyword}"')

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
        """Convert Immich assets to ImageHolder objects that BaseService can use."""
        logging.info(f'Parsing {len(data)} assets for keyword "{keyword}"')
        result = []

        supported_images = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/webp', 'image/tiff', 'image/tif', 'image/bmp',
            'image/heic', 'image/heif'
        }

        api_base = self._getApiBaseUrl()
        config = self.getImmichConfiguration()
        server_url = config.get('server_url', '') if config else ''

        for i, asset in enumerate(data):
            asset_id = asset.get('id')
            if not asset_id:
                logging.warning(f'Asset {i + 1} missing ID, skipping')
                continue

            asset_type = asset.get('type')
            if asset_type == 'VIDEO':
                logging.debug(f'Asset {i + 1}: skipping video {asset_id}')
                continue

            mime_type = asset.get('originalMimeType') or asset.get('mimeType')

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
                    logging.debug(f'Asset {i + 1}: defaulting to image/jpeg for {asset_id}')

            if mime_type not in supported_images:
                logging.debug(f'Asset {i + 1}: skipping unsupported type {mime_type}')
                continue

            image = self.createImageHolder()
            image.setId(asset_id)
            image.setMimetype(mime_type)

            if api_base:
                image.url = f'{api_base}/assets/{asset_id}/thumbnail?size=preview'

            original_filename = asset.get('originalFileName')
            if original_filename:
                image.setFilename(original_filename)

            exif_info = asset.get('exifInfo', {}) or {}
            width = exif_info.get('exifImageWidth')
            height = exif_info.get('exifImageHeight')

            if not width or not height:
                width = asset.get('width')
                height = asset.get('height')

            if width and height:
                try:
                    image.setDimensions(int(width), int(height))
                except (ValueError, TypeError):
                    logging.debug(f'Asset {i + 1}: invalid dimensions for {asset_id}')

            image.allowCache(True)

            if server_url:
                image.source = f'{server_url}/photos/{asset_id}'

            result.append(image)
            logging.debug(f'Added asset {asset_id} ({mime_type}) with dimensions {width}x{height}')

        logging.info(f'Parsed {len(result)} supported images from {len(data)} total assets')
        return result

    def getContentUrl(self, image, hints):
        api_base = self._getApiBaseUrl()
        if not api_base:
            return None
        asset_id = image.id
        if not asset_id:
            return None

        endpoint = 'thumbnail?size=preview'

        if image.dimensions:
            width = image.dimensions.get('width', 0)
            height = image.dimensions.get('height', 0)
            if width > 0 and height > 0 and self._canProcessFullRes(width, height):
                disp = hints.get('display', {}) if hints else {}
                max_display = max(disp.get('width', 0), disp.get('height', 0))
                if max_display > 1920:
                    endpoint = 'original'
                else:
                    endpoint = 'thumbnail?size=fullsize'

        return f'{api_base}/assets/{asset_id}/{endpoint}'

    def _canProcessFullRes(self, width, height):
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
        """Override to add Immich authentication headers."""
        config = self.getImmichConfiguration()

        if config and 'server_url' in config and url and url.startswith(config['server_url']):
            headers = {'x-api-key': config['api_key']}

            tries = 0
            while tries < 5:
                try:
                    method = 'POST' if usePost else 'GET'
                    r = requests.request(
                        method,
                        url,
                        params=params,
                        json=data,
                        headers=headers,
                        timeout=180,
                        stream=not usePost
                    )
                    break
                except requests.exceptions.RequestException as e:
                    logging.exception(f'Issues downloading from Immich (attempt {tries + 1})')
                    if tries == 4:
                        raise RequestNoNetwork(f'Failed to connect to Immich: {e}')

                time.sleep(tries * 10)
                tries += 1
                logging.warning(f'Retrying Immich request, attempt #{tries + 1}')

            if tries == 5:
                logging.error('Failed to download from Immich due to network issues')
                raise RequestNoNetwork('Network timeout')

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
        if self.hasImmichConfiguration():
            api_info = self._STATE.get(self.API_INFO_STATE_KEY)
            api_label = ''
            if api_info:
                api_label = f' Detected Immich API v{api_info.get("api_version")}.'
            msgs.append({
                'level': 'INFO',
                'message': f'Immich service configured and ready. Photo retrieval available for added albums.{api_label}',
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
