#!/usr/bin/env python3
#
# Tests for the display's mode list and mode changes under KMS (#97), against a
# fake /sys/class/drm and cmdline.txt. Run from the repository root:
#
#   python3 -m unittest
#
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import modules.kms as kms
from modules.path import path
from modules.display import display

from tests.test_kms import MONITOR_1080P


class TestDisplayKms(unittest.TestCase):
  BASE = 'console=tty1 root=PARTUUID=1234-02 rootwait'

  def setUp(self):
    self.folder = tempfile.mkdtemp()
    self.saved = (kms.DRM_ROOT, path.CMDLINE_TXT)
    kms.DRM_ROOT = os.path.join(self.folder, 'drm')
    path.CMDLINE_TXT = Path(self.folder) / 'cmdline.txt'
    os.mkdir(kms.DRM_ROOT)
    self.writeCmdline(self.BASE + '\n')

  def tearDown(self):
    kms.DRM_ROOT, path.CMDLINE_TXT = self.saved
    shutil.rmtree(self.folder)

  def connector(self, name, status='connected', edid=MONITOR_1080P, modes=('1920x1080', '1280x720')):
    base = os.path.join(kms.DRM_ROOT, f'card1-{name}')
    os.mkdir(base)
    with open(os.path.join(base, 'status'), 'w') as f:
      f.write(status + '\n')
    with open(os.path.join(base, 'edid'), 'wb') as f:
      f.write(edid or b'')
    with open(os.path.join(base, 'modes'), 'w') as f:
      f.write(''.join(f'{m}\n' for m in modes))

  def writeCmdline(self, text):
    with open(path.CMDLINE_TXT, 'w') as f:
      f.write(text)

  def readCmdline(self):
    with open(path.CMDLINE_TXT) as f:
      return f.read()

  def values(self):
    return [e['value'] for e in display.kmsModes()]

  def test_mode_list(self):
    self.connector('HDMI-A-1')
    self.connector('HDMI-A-2', status='disconnected')
    os.symlink(os.path.join(kms.DRM_ROOT, 'card1-HDMI-A-1'), os.path.join(kms.DRM_ROOT, 'card1'))
    values = self.values()
    self.assertEqual(values[0], 'HDMI-A-1:auto')
    self.assertEqual(values[1], 'HDMI-A-1:1920x1080@60')
    self.assertIn('HDMI-A-1:1280x720', values)
    self.assertFalse(any(v.startswith('HDMI-A-2') for v in values))

  def test_no_display(self):
    self.assertEqual(display.kmsModes(), [])
    self.assertEqual(display.configuredMode(), 'auto')

  def test_way_back_to_larger_mode(self):
    # QA failure 1: booted at 1280x720, the kernel lists only smaller modes
    self.connector('HDMI-A-1', modes=('1280x720', '800x600', '720x480', '640x480'))
    self.writeCmdline(self.BASE + ' video=HDMI-A-1:1280x720@60\n')
    self.assertEqual(display.configuredMode(), 'HDMI-A-1:1280x720@60')
    self.assertTrue(display.isModeAvailable('HDMI-A-1:1920x1080@60'))
    self.assertTrue(display.applyMode('HDMI-A-1:1920x1080@60'))
    self.assertEqual(self.readCmdline(), self.BASE + ' video=HDMI-A-1:1920x1080@60\n')
    self.assertTrue(display.applyMode('HDMI-A-1:auto'))
    self.assertEqual(self.readCmdline(), self.BASE + '\n')
    self.assertEqual(display.configuredMode('HDMI-A-1'), 'HDMI-A-1:auto')

  def test_refused_mode_changes_nothing(self):
    # QA failure 2: a refused mode must leave cmdline.txt and the configured mode alone
    self.connector('HDMI-A-1')
    self.writeCmdline(self.BASE + ' video=HDMI-A-1:1280x720@60\n')
    for value in ['HDMI-A-1:1024x600@60', 'HDMI-A-2:1920x1080@60', 'DMT 82 DVI', 'auto', '']:
      self.assertFalse(display.isModeAvailable(value), value)
    self.assertEqual(self.readCmdline(), self.BASE + ' video=HDMI-A-1:1280x720@60\n')
    self.assertEqual(display.configuredMode('HDMI-A-1'), 'HDMI-A-1:1280x720@60')

  def test_same_mode_is_no_change(self):
    self.connector('HDMI-A-1')
    self.writeCmdline(self.BASE + ' video=HDMI-A-1:1920x1080@60\n')
    self.assertFalse(display.applyMode('HDMI-A-1:1920x1080@60'))

  def test_hand_written_mode_is_listed_and_kept(self):
    # A panel without EDID, set up by hand as the README describes
    self.connector('HDMI-A-1', edid=None, modes=('1366x768', '1024x768'))
    self.writeCmdline(self.BASE + ' video=HDMI-A-1:1366x768MR@60D,rotate=180\n')
    self.assertEqual(display.configuredMode(), 'HDMI-A-1:1366x768@60')
    entries = display.kmsModes()
    self.assertEqual(entries[1]['value'], 'HDMI-A-1:1366x768@60')
    self.assertEqual(entries[1]['label'], '1366x768@60 (set in cmdline.txt)')
    # Choosing it again leaves the hand-written timing flags alone
    self.assertFalse(display.applyMode('HDMI-A-1:1366x768@60'))
    # Another mode keeps the D flag and rotate=
    self.assertTrue(display.applyMode('HDMI-A-1:1024x768'))
    self.assertEqual(self.readCmdline(), self.BASE + ' video=HDMI-A-1:1024x768D,rotate=180\n')
    self.assertTrue(display.applyMode('HDMI-A-1:auto'))
    self.assertEqual(self.readCmdline(), self.BASE + ' video=HDMI-A-1:D,rotate=180\n')

  def test_two_displays(self):
    self.connector('HDMI-A-1')
    self.connector('HDMI-A-2', modes=('1024x768',), edid=None)
    self.writeCmdline(self.BASE + ' video=HDMI-A-2:1024x768\n')
    self.assertEqual(display.configuredMode(), 'HDMI-A-1:auto')
    self.assertEqual(display.configuredMode('HDMI-A-2'), 'HDMI-A-2:1024x768')
    self.assertIn('HDMI-A-2: Automatic (display\'s preferred mode)', [e['label'] for e in display.kmsModes()])

  def test_size(self):
    self.connector('HDMI-A-1')
    self.assertEqual(display._kmsSize('HDMI-A-1:auto'), (1920, 1080))
    self.assertEqual(display._kmsSize('HDMI-A-1:1280x720@60'), (1280, 720))
    self.assertIsNone(display._kmsSize('HDMI-A-1:NTSC'))


if __name__ == '__main__':
  unittest.main()
