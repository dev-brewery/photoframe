import tempfile
import unittest
from unittest.mock import patch

import requests

from services.svc_immich import Immich
from services.svc_immich import ImmichSchemaError
from services.svc_immich import ImmichV2Api
from services.svc_immich import ImmichV3Api
from modules.network import RequestResult


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b'', headers=None, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.headers = headers or {'Content-Type': 'application/json'}
        self._json_error = json_error

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    def iter_content(self, chunk_size=8192):
        yield self.content


def sample_asset(asset_id='asset-1', mime_type='image/jpeg'):
    return {
        'id': asset_id,
        'type': 'IMAGE',
        'originalMimeType': mime_type,
        'originalFileName': 'photo.jpg',
        'width': 1024,
        'height': 768,
        'exifInfo': {'exifImageWidth': 1024, 'exifImageHeight': 768}
    }


class ImmichServiceTests(unittest.TestCase):
    def make_service(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        svc = Immich(tempdir.name, 'svc', 'Immich')
        svc.setImmichConfiguration({
            'server_url': 'https://immich.example.com',
            'api_key': 'test-key'
        })
        svc._STATE['_KEYWORDS'] = ['Album']
        svc.setExtras({
            'Album': {
                'albumId': 'album-1',
                'sourceUrl': 'https://immich.example.com/albums/album-1',
                'albumName': 'Album'
            }
        })
        return svc

    @patch('services.svc_immich.requests.request')
    def test_detects_v2_api_from_server_version(self, request_mock):
        request_mock.return_value = FakeResponse(payload={'major': 2, 'minor': 7, 'patch': 5})
        svc = self.make_service()

        api = svc._getImmichApi()

        self.assertIsInstance(api, ImmichV2Api)
        self.assertEqual(svc._STATE['_IMMICH_API_INFO']['api_version'], 2)
        self.assertEqual(svc._STATE['_IMMICH_API_INFO']['api_prefix'], '/api')

    @patch('services.svc_immich.requests.request')
    def test_detects_v3_api_from_server_version(self, request_mock):
        request_mock.return_value = FakeResponse(payload={'major': 3, 'minor': 0, 'patch': 0, 'prerelease': None})
        svc = self.make_service()

        api = svc._getImmichApi()

        self.assertIsInstance(api, ImmichV3Api)
        self.assertEqual(svc._STATE['_IMMICH_API_INFO']['api_version'], 3)

    @patch('services.svc_immich.requests.request')
    def test_rejects_html_app_shell_when_detecting_no_prefix_endpoint(self, request_mock):
        request_mock.side_effect = [
            FakeResponse(status_code=404),
            FakeResponse(payload=None, content=b'<html></html>', json_error=ValueError('not json'))
        ]
        svc = self.make_service()

        with self.assertRaises(ImmichSchemaError):
            svc._getImmichApi(forceDetect=True)

        self.assertEqual(request_mock.call_count, 2)
        self.assertEqual(request_mock.call_args_list[1][0][1], 'https://immich.example.com/server/version')

    @patch('services.svc_immich.requests.request')
    def test_v2_indexing_uses_embedded_album_assets(self, request_mock):
        request_mock.side_effect = [
            FakeResponse(payload={'major': 2, 'minor': 7, 'patch': 5}),
            FakeResponse(payload={'id': 'album-1', 'assets': [sample_asset()]})
        ]
        svc = self.make_service()

        images = svc.getImagesFor('Album')

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].id, 'asset-1')
        self.assertEqual(images[0].url, 'https://immich.example.com/api/assets/asset-1/thumbnail?size=preview')
        self.assertEqual(request_mock.call_args_list[1][0][0], 'GET')
        self.assertEqual(request_mock.call_args_list[1][0][1], 'https://immich.example.com/api/albums/album-1')

    @patch('services.svc_immich.requests.request')
    def test_v3_indexing_uses_large_asset_search_json_body(self, request_mock):
        request_mock.side_effect = [
            FakeResponse(payload={'major': 3, 'minor': 0, 'patch': 0, 'prerelease': None}),
            FakeResponse(payload=[sample_asset()])
        ]
        svc = self.make_service()

        images = svc.getImagesFor('Album')

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].id, 'asset-1')
        self.assertEqual(request_mock.call_args_list[1][0][0], 'POST')
        self.assertEqual(request_mock.call_args_list[1][0][1], 'https://immich.example.com/api/search/large-assets')
        data = request_mock.call_args_list[1][1]['json']
        self.assertEqual(data['albumIds'], ['album-1'])
        self.assertEqual(data['type'], 'IMAGE')
        self.assertTrue(data['withExif'])

    @patch('services.svc_immich.requests.request')
    def test_auth_failure_surfaces_as_image_error(self, request_mock):
        request_mock.return_value = FakeResponse(status_code=401, payload={'message': 'Unauthorized'})
        svc = self.make_service()

        images = svc.getImagesFor('Album')

        self.assertEqual(len(images), 1)
        self.assertIn('Authentication failed', images[0].error)

    @patch('services.svc_immich.requests.request')
    def test_transient_network_failure_is_not_cached_as_empty_album(self, request_mock):
        request_mock.side_effect = requests.exceptions.ConnectionError('dns failed')
        svc = self.make_service()

        images = svc._getImagesFor('Album')

        self.assertIsNone(images)
        self.assertNotIn('Album', svc._STATE['_NUM_IMAGES'])
        self.assertNotIn('Album', svc._STATE['_NEXT_SCAN'])

    @patch('services.svc_immich.requests.request')
    def test_downloads_send_api_key_header(self, request_mock):
        request_mock.return_value = FakeResponse(
            payload=None,
            content=b'image-bytes',
            headers={'Content-Type': 'image/jpeg'}
        )
        svc = self.make_service()

        result = svc.requestUrl('https://immich.example.com/api/assets/asset-1/thumbnail?size=preview')

        self.assertTrue(result.isSuccess())
        self.assertEqual(result.content, b'image-bytes')
        self.assertEqual(request_mock.call_args_list[0][1]['headers']['x-api-key'], 'test-key')

    @patch('services.svc_immich.requests.request')
    def test_failed_download_uses_existing_request_result(self, request_mock):
        request_mock.return_value = FakeResponse(status_code=500, payload={'message': 'failed'})
        svc = self.make_service()

        result = svc.requestUrl('https://immich.example.com/api/assets/asset-1/thumbnail?size=preview')

        self.assertEqual(result.httpcode, 500)
        self.assertEqual(result.result, RequestResult.UNKNOWN)


if __name__ == '__main__':
    unittest.main()
