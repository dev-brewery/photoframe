#!/usr/bin/env python3
#
# Tests for display mode selection under KMS (#97): the EDID parser, the
# setting values and the cmdline.txt editor. Run from the repository root:
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
from modules.sysconfig import sysconfig


def dtd(width, height, hblank, vblank, clock_khz, interlaced=False):
  # An 18-byte detailed timing descriptor; for interlaced modes height is per field
  clock = clock_khz // 10
  d = bytearray(18)
  d[0] = clock & 0xFF
  d[1] = clock >> 8
  d[2] = width & 0xFF
  d[3] = hblank & 0xFF
  d[4] = ((width >> 8) << 4) | (hblank >> 8)
  d[5] = height & 0xFF
  d[6] = vblank & 0xFF
  d[7] = ((height >> 8) << 4) | (vblank >> 8)
  d[17] = 0x80 if interlaced else 0x18
  return bytes(d)


def monitorName(name):
  d = bytearray(18)
  d[3] = 0xFC
  d[5:5 + len(name)] = name.encode()
  return bytes(d)


def edid(descriptors, standard=(), established=(0, 0, 0), extensions=()):
  b = bytearray(128)
  b[0:8] = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])
  b[18], b[19] = 1, 4
  b[35:38] = bytes(established)
  for i in range(8):
    b[38 + i * 2:40 + i * 2] = bytes(standard[i]) if i < len(standard) else b'\x01\x01'
  for i in range(4):
    b[54 + i * 18:72 + i * 18] = descriptors[i] if i < len(descriptors) else monitorName('')
  b[126] = len(extensions)
  return bytes(b) + b''.join(extensions)


def cta(vics, dtds=()):
  b = bytearray(128)
  b[0], b[1] = 0x02, 0x03
  block = bytes([(2 << 5) | len(vics)]) + bytes(vics)
  b[2] = 4 + len(block)
  b[4:4 + len(block)] = block
  o = b[2]
  for d in dtds:
    b[o:o + 18] = d
    o += 18
  return bytes(b)


MONITOR_1080P = edid(
  [dtd(1920, 1080, 280, 45, 148500), monitorName('TEST')],
  standard=[(0xD1, 0xC0), (0x81, 0x80)],   # 1920x1080@60 16:9, 1280x1024@60 5:4
  established=(0x21, 0x08, 0x00),          # 640x480@60, 800x600@60, 1024x768@60
)

TV_4K = edid(
  [dtd(3840, 2160, 560, 90, 594000), monitorName('TV')],
  extensions=[cta([16, 4, 128 + 3, 5, 97, 200], [dtd(1280, 720, 370, 30, 74250)])],
)


def sizes(modes):
  return [kms.modeString(m) for m in modes]


class TestEdid(unittest.TestCase):
  def test_monitor(self):
    modes = kms.parseEdid(MONITOR_1080P)
    self.assertEqual(sizes(modes), ['1920x1080@60', '1280x1024@60', '640x480@60', '800x600@60', '1024x768@60'])
    self.assertTrue(modes[0]['preferred'])
    self.assertFalse(any(m['preferred'] for m in modes[1:]))

  def test_tv_with_cta_block(self):
    modes = kms.parseEdid(TV_4K)
    self.assertEqual(modes[0], {'width': 3840, 'height': 2160, 'rate': 60, 'interlaced': False, 'preferred': True})
    found = sizes(modes)
    # VIC 16, 4, 3 (marked native), 5 (interlaced), 97, and the CTA block's detailed timing;
    # VIC 200 is not in the table and is skipped
    for expected in ['1920x1080@60', '1280x720@60', '720x480@60', '3840x2160@60', '1920x1080@60i']:
      self.assertIn(expected, found)
    self.assertEqual(found.count('3840x2160@60'), 1)
    self.assertEqual(found.count('1280x720@60'), 1)

  def test_interlaced_dtd(self):
    modes = kms.parseEdid(edid([dtd(1920, 540, 280, 22, 74250, interlaced=True)]))
    self.assertEqual(sizes(modes), ['1920x1080@60i'])

  def test_invalid(self):
    self.assertEqual(kms.parseEdid(None), [])
    self.assertEqual(kms.parseEdid(b''), [])
    self.assertEqual(kms.parseEdid(b'\x00' * 128), [])
    self.assertEqual(kms.parseEdid(MONITOR_1080P[:100]), [])

  def test_sysfs_modes(self):
    modes = kms.parseSysfsModes(['1920x1080', '1920x1080', '1920x1080i', '1280x720', ''])
    self.assertEqual(sizes(modes), ['1920x1080', '1920x1080i', '1280x720'])
    self.assertTrue(modes[0]['preferred'])

  def test_edid_wins_over_truncated_sysfs_list(self):
    # After booting at 1280x720 the kernel lists only smaller modes; the EDID still has them all
    connector = {'name': 'HDMI-A-1', 'edid': MONITOR_1080P, 'modes': ['1280x720', '800x600', '640x480']}
    found = sizes(kms.connectorModes(connector))
    self.assertIn('1920x1080@60', found)
    self.assertIn('1280x720', found)          # only the kernel lists it
    self.assertNotIn('800x600', found)        # the EDID has 800x600@60

  def test_no_edid_uses_sysfs(self):
    connector = {'name': 'HDMI-A-1', 'edid': None, 'modes': ['1366x768', '1024x768']}
    self.assertEqual(sizes(kms.connectorModes(connector)), ['1366x768', '1024x768'])


class TestValues(unittest.TestCase):
  def test_normalize(self):
    self.assertEqual(kms.normalizeValue('HDMI-A-1:1920x1080@60'), 'HDMI-A-1:1920x1080@60')
    self.assertEqual(kms.normalizeValue(' HDMI-A-1:auto '), 'HDMI-A-1:auto')
    self.assertEqual(kms.normalizeValue('HDMI-A-1:1920x1080i'), 'HDMI-A-1:1920x1080i')
    self.assertIsNone(kms.normalizeValue('DMT 82 DVI'))
    self.assertIsNone(kms.normalizeValue('HDMI-A-1:1920x1080MR@60D'))
    self.assertIsNone(kms.normalizeValue('HDMI A:1920x1080'))

  def test_cmdline_mode_to_setting(self):
    self.assertEqual(kms.cmdlineModeToSetting(''), 'auto')
    self.assertEqual(kms.cmdlineModeToSetting('D'), 'auto')
    self.assertEqual(kms.cmdlineModeToSetting('1366x768MR@60D'), '1366x768@60')
    self.assertEqual(kms.cmdlineModeToSetting('1920x1080-24@50i'), '1920x1080@50i')
    self.assertEqual(kms.cmdlineModeToSetting('NTSC'), 'NTSC')

  def test_setting_to_cmdline_mode(self):
    mode = kms.parseSettingMode('1920x1080@60')
    self.assertEqual(kms.settingToCmdlineMode(mode, ''), '1920x1080@60')
    # The force flag, bpp and margins are kept; M and R are dropped
    self.assertEqual(kms.settingToCmdlineMode(mode, '1366x768MR@60D'), '1920x1080@60D')
    self.assertEqual(kms.settingToCmdlineMode(mode, '1280x720-24@60me'), '1920x1080-24@60me')
    self.assertEqual(kms.settingToCmdlineMode(None, '1366x768MR@60D'), 'D')
    self.assertEqual(kms.settingToCmdlineMode(None, '1280x720'), '')
    self.assertEqual(kms.settingToCmdlineMode(kms.parseSettingMode('1920x1080i'), 'NTSC'), '1920x1080i')

  def test_entries(self):
    modes = kms.sortModes(kms.parseEdid(MONITOR_1080P))
    entries = [kms.entry('HDMI-A-1', None)] + [kms.entry('HDMI-A-1', m) for m in modes]
    self.assertEqual(entries[0]['value'], 'HDMI-A-1:auto')
    self.assertEqual(entries[1]['value'], 'HDMI-A-1:1920x1080@60')
    self.assertEqual(entries[1]['label'], '1920x1080 (60Hz), preferred')
    self.assertTrue(kms.isAvailable('HDMI-A-1:1280x1024@60', entries))
    self.assertFalse(kms.isAvailable('HDMI-A-1:1280x720@60', entries))
    self.assertFalse(kms.isAvailable('HDMI-A-2:1920x1080@60', entries))
    self.assertEqual(kms.entry('HDMI-A-2', None, multiple=True)['label'], 'HDMI-A-2: Automatic (display\'s preferred mode)')


class TestCmdline(unittest.TestCase):
  BASE = 'console=serial0,115200 console=tty1 root=PARTUUID=1234-02 rootfstype=ext4 fsck.repair=yes rootwait'

  def replace(self, line, mode, connector='HDMI-A-1'):
    return sysconfig.replaceVideoMode(line, connector, mode)

  def test_add(self):
    self.assertEqual(self.replace(self.BASE + '\n', '1280x720@60'), self.BASE + ' video=HDMI-A-1:1280x720@60\n')
    self.assertEqual(self.replace(self.BASE, '1280x720@60'), self.BASE + ' video=HDMI-A-1:1280x720@60\n')
    self.assertEqual(self.replace(self.BASE + '\n', ''), self.BASE + '\n')

  def test_replace_keeps_options(self):
    line = self.BASE + ' video=HDMI-A-1:1920x1080@60,rotate=180 quiet\n'
    self.assertEqual(self.replace(line, '1280x720@60'), self.BASE + ' video=HDMI-A-1:1280x720@60,rotate=180 quiet\n')
    self.assertEqual(self.replace(line, ''), self.BASE + ' video=HDMI-A-1:rotate=180 quiet\n')
    standalone = self.BASE + ' video=HDMI-A-1:rotate=180\n'
    self.assertEqual(self.replace(standalone, '1280x720@60'), self.BASE + ' video=HDMI-A-1:1280x720@60,rotate=180\n')
    self.assertEqual(sysconfig.getVideoModes(standalone), {'HDMI-A-1': ''})

  def test_remove(self):
    self.assertEqual(self.replace(self.BASE + ' video=HDMI-A-1:1280x720@60\n', ''), self.BASE + '\n')
    self.assertEqual(self.replace('video=HDMI-A-1:1280x720 ' + self.BASE + '\n', ''), self.BASE + '\n')
    self.assertEqual(self.replace(self.BASE + ' video=HDMI-A-1:1280x720 quiet\n', ''), self.BASE + ' quiet\n')

  def test_other_connectors_untouched(self):
    line = self.BASE + ' video=HDMI-A-2:1024x768@60 video=HDMI-A-1:1280x720@60\n'
    self.assertEqual(self.replace(line, '1920x1080@60'), self.BASE + ' video=HDMI-A-2:1024x768@60 video=HDMI-A-1:1920x1080@60\n')
    self.assertEqual(sysconfig.getVideoModes(line), {'HDMI-A-2': '1024x768@60', 'HDMI-A-1': '1280x720@60'})
    self.assertEqual(self.replace(self.BASE + ' video=HDMI-A-10:800x600\n', '1920x1080@60'),
                     self.BASE + ' video=HDMI-A-10:800x600 video=HDMI-A-1:1920x1080@60\n')

  def test_set_video_mode_file(self):
    folder = tempfile.mkdtemp()
    saved = path.CMDLINE_TXT
    try:
      path.CMDLINE_TXT = Path(folder) / 'cmdline.txt'
      with open(path.CMDLINE_TXT, 'w') as f:
        f.write(self.BASE + '\n')
      self.assertTrue(sysconfig.setVideoMode('HDMI-A-1', '1280x720@60'))
      self.assertFalse(sysconfig.setVideoMode('HDMI-A-1', '1280x720@60'))
      with open(path.CMDLINE_TXT) as f:
        self.assertEqual(f.read(), self.BASE + ' video=HDMI-A-1:1280x720@60\n')
      with open(f'{path.CMDLINE_TXT}.original') as f:
        self.assertEqual(f.read(), self.BASE + '\n')
      self.assertTrue(sysconfig.setVideoMode('HDMI-A-1', ''))
      with open(path.CMDLINE_TXT) as f:
        self.assertEqual(f.read(), self.BASE + '\n')
      os.unlink(path.CMDLINE_TXT)
      self.assertIsNone(sysconfig.setVideoMode('HDMI-A-1', '1280x720@60'))
    finally:
      path.CMDLINE_TXT = saved
      shutil.rmtree(folder)


if __name__ == '__main__':
  unittest.main()
