#!/usr/bin/env python3
#
# Tests for PUT /setting/tvservice under KMS (#97). Needs flask. Run from the
# repository root:
#
#   python3 -m unittest
#
import os
import shutil
import tempfile
import unittest
from pathlib import Path

try:
  from flask import Flask
except ImportError:
  Flask = None

import modules.kms as kms
from modules.path import path

from tests.test_kms import MONITOR_1080P


class FakeServer:
  def __init__(self, app):
    self.app = app


@unittest.skipIf(Flask is None, 'flask is not installed')
class TestSettingsRoute(unittest.TestCase):
  BASE = 'console=tty1 root=PARTUUID=1234-02 rootwait'

  def setUp(self):
    from modules.display import display
    from modules.settings import settings
    from routes.settings import RouteSettings

    self.folder = tempfile.mkdtemp()
    self.saved = (kms.DRM_ROOT, path.CMDLINE_TXT, path.CONFIGFOLDER, path.CONFIGFILE)
    kms.DRM_ROOT = os.path.join(self.folder, 'drm')
    path.CMDLINE_TXT = Path(self.folder) / 'cmdline.txt'
    path.CONFIGFOLDER = Path(self.folder)
    path.CONFIGFILE = Path(self.folder) / 'settings.json'

    connector = os.path.join(kms.DRM_ROOT, 'card1-HDMI-A-1')
    os.makedirs(connector)
    with open(os.path.join(connector, 'status'), 'w') as f:
      f.write('connected\n')
    with open(os.path.join(connector, 'edid'), 'wb') as f:
      f.write(MONITOR_1080P)
    with open(os.path.join(connector, 'modes'), 'w') as f:
      f.write('1280x720\n')
    self.writeCmdline(self.BASE + ' video=HDMI-A-1:1280x720@60\n')

    self.display = display()
    self.settings = settings()
    self.settings.setUser('tvservice', 'HDMI-A-1:1280x720@60')

    app = Flask(__name__)
    route = RouteSettings()
    route.setupex(None, self.settings, None, None, self.display, None, None)
    route._assignServer(FakeServer(app))
    for mapping in route._MAPPINGS:
      app.add_url_rule(mapping._URL, mapping._URL, route, methods=mapping._METHODS, defaults=mapping._DEFAULTS)
    self.client = app.test_client()

  def tearDown(self):
    kms.DRM_ROOT, path.CMDLINE_TXT, path.CONFIGFOLDER, path.CONFIGFILE = self.saved
    shutil.rmtree(self.folder)

  def writeCmdline(self, text):
    with open(path.CMDLINE_TXT, 'w') as f:
      f.write(text)

  def readCmdline(self):
    with open(path.CMDLINE_TXT) as f:
      return f.read()

  def put(self, value):
    return self.client.put('/setting/tvservice/' + value)

  def test_offered_mode(self):
    self.assertFalse(self.display.has_tvservice)
    response = self.put('HDMI-A-1:1920x1080@60')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.get_json(), {'status': True, 'reboot': True})
    self.assertEqual(self.readCmdline(), self.BASE + ' video=HDMI-A-1:1920x1080@60\n')
    self.assertEqual(self.settings.getUser('tvservice'), 'HDMI-A-1:1920x1080@60')

  def test_same_mode_needs_no_reboot(self):
    response = self.put('HDMI-A-1:1280x720@60')
    self.assertEqual(response.get_json(), {'status': True, 'reboot': False})

  def test_refused_mode_changes_nothing(self):
    for value in ['HDMI-A-1:1024x600@60', 'HDMI-A-2:1920x1080@60', 'DMT 82 DVI']:
      response = self.put(value)
      self.assertEqual(response.status_code, 400, value)
      self.assertFalse(response.get_json()['status'])
    self.assertEqual(self.readCmdline(), self.BASE + ' video=HDMI-A-1:1280x720@60\n')
    self.assertEqual(self.settings.getUser('tvservice'), 'HDMI-A-1:1280x720@60')
    self.assertFalse(os.path.exists(path.CONFIGFILE))

  def test_unwritable_cmdline(self):
    os.unlink(path.CMDLINE_TXT)
    response = self.put('HDMI-A-1:1920x1080@60')
    self.assertEqual(response.status_code, 500)
    self.assertEqual(self.settings.getUser('tvservice'), 'HDMI-A-1:1280x720@60')


if __name__ == '__main__':
  unittest.main()
