#!/usr/bin/env python3
#
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
# Display modes under the KMS driver (#97), where tvservice does not exist.
#
# The modes offered are read from the display's EDID. The kernel's own list
# (/sys/class/drm/*/modes) is only a fallback: after booting with a smaller
# video= mode it no longer lists the larger modes, so it cannot offer a way back.
#
# A mode is chosen by writing video=<connector>:<mode> into cmdline.txt and
# takes effect after a reboot. The setting holds "<connector>:<mode>", where
# <mode> is WxH[@rate][i] or "auto" (no mode, the display's preferred one).
#
import os
import re

DRM_ROOT = '/sys/class/drm'

AUTO = 'auto'

# CTA-861 video identification codes: (width, height, rate, interlaced).
# Pixel-repeated modes are listed with the width the kernel reports.
_VIC = {
  1: (640, 480, 60, False),     2: (720, 480, 60, False),     3: (720, 480, 60, False),
  4: (1280, 720, 60, False),    5: (1920, 1080, 60, True),    6: (720, 480, 60, True),
  7: (720, 480, 60, True),      8: (720, 240, 60, False),     9: (720, 240, 60, False),
  10: (2880, 480, 60, True),    11: (2880, 480, 60, True),    12: (2880, 240, 60, False),
  13: (2880, 240, 60, False),   14: (1440, 480, 60, False),   15: (1440, 480, 60, False),
  16: (1920, 1080, 60, False),  17: (720, 576, 50, False),    18: (720, 576, 50, False),
  19: (1280, 720, 50, False),   20: (1920, 1080, 50, True),   21: (720, 576, 50, True),
  22: (720, 576, 50, True),     23: (720, 288, 50, False),    24: (720, 288, 50, False),
  25: (2880, 576, 50, True),    26: (2880, 576, 50, True),    27: (2880, 288, 50, False),
  28: (2880, 288, 50, False),   29: (1440, 576, 50, False),   30: (1440, 576, 50, False),
  31: (1920, 1080, 50, False),  32: (1920, 1080, 24, False),  33: (1920, 1080, 25, False),
  34: (1920, 1080, 30, False),  35: (2880, 480, 60, False),   36: (2880, 480, 60, False),
  37: (2880, 576, 50, False),   38: (2880, 576, 50, False),   39: (1920, 1080, 50, True),
  40: (1920, 1080, 100, True),  41: (1280, 720, 100, False),  42: (720, 576, 100, False),
  43: (720, 576, 100, False),   44: (720, 576, 100, True),    45: (720, 576, 100, True),
  46: (1920, 1080, 120, True),  47: (1280, 720, 120, False),  48: (720, 480, 120, False),
  49: (720, 480, 120, False),   50: (720, 480, 120, True),    51: (720, 480, 120, True),
  52: (720, 576, 200, False),   53: (720, 576, 200, False),   54: (720, 576, 200, True),
  55: (720, 576, 200, True),    56: (720, 480, 240, False),   57: (720, 480, 240, False),
  58: (720, 480, 240, True),    59: (720, 480, 240, True),    60: (1280, 720, 24, False),
  61: (1280, 720, 25, False),   62: (1280, 720, 30, False),   63: (1920, 1080, 120, False),
  64: (1920, 1080, 100, False), 65: (1280, 720, 24, False),   66: (1280, 720, 25, False),
  67: (1280, 720, 30, False),   68: (1280, 720, 50, False),   69: (1280, 720, 60, False),
  70: (1280, 720, 100, False),  71: (1280, 720, 120, False),  72: (1920, 1080, 24, False),
  73: (1920, 1080, 25, False),  74: (1920, 1080, 30, False),  75: (1920, 1080, 50, False),
  76: (1920, 1080, 60, False),  77: (1920, 1080, 100, False), 78: (1920, 1080, 120, False),
  79: (1680, 720, 24, False),   80: (1680, 720, 25, False),   81: (1680, 720, 30, False),
  82: (1680, 720, 50, False),   83: (1680, 720, 60, False),   84: (1680, 720, 100, False),
  85: (1680, 720, 120, False),  86: (2560, 1080, 24, False),  87: (2560, 1080, 25, False),
  88: (2560, 1080, 30, False),  89: (2560, 1080, 50, False),  90: (2560, 1080, 60, False),
  91: (2560, 1080, 100, False), 92: (2560, 1080, 120, False), 93: (3840, 2160, 24, False),
  94: (3840, 2160, 25, False),  95: (3840, 2160, 30, False),  96: (3840, 2160, 50, False),
  97: (3840, 2160, 60, False),  98: (4096, 2160, 24, False),  99: (4096, 2160, 25, False),
  100: (4096, 2160, 30, False), 101: (4096, 2160, 50, False), 102: (4096, 2160, 60, False),
  103: (3840, 2160, 24, False), 104: (3840, 2160, 25, False), 105: (3840, 2160, 30, False),
  106: (3840, 2160, 50, False), 107: (3840, 2160, 60, False),
}

# EDID established timings, bytes 35-37, most significant bit first
_ESTABLISHED = [
  (720, 400, 70, False), (720, 400, 88, False), (640, 480, 60, False), (640, 480, 67, False),
  (640, 480, 72, False), (640, 480, 75, False), (800, 600, 56, False), (800, 600, 60, False),
  (800, 600, 72, False), (800, 600, 75, False), (832, 624, 75, False), (1024, 768, 87, True),
  (1024, 768, 60, False), (1024, 768, 70, False), (1024, 768, 75, False), (1280, 1024, 75, False),
  (1152, 870, 75, False),
]

_EDID_HEADER = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])

# The mode part of video=<connector>:<mode>, as the kernel parses it:
# <xres>x<yres>[M][R][-<bpp>][@<refresh>][i][m][eDd]
_CMDLINE_MODE = re.compile(r'^(\d+)x(\d+)(M?)(R?)(?:-(\d+))?(?:@(\d+))?(i?)(m?)([eDd]?)$')
_FLAGS_ONLY = re.compile(r'^[eDd]?$')

# The mode part of a setting value: WxH[@rate][i]
_SETTING_MODE = re.compile(r'^(\d+)x(\d+)(?:@(\d+))?(i?)$')


def _mode(width, height, rate, interlaced, preferred=False):
  return {'width': width, 'height': height, 'rate': rate, 'interlaced': interlaced, 'preferred': preferred}


def _detailedTiming(d, preferred):
  # An 18-byte detailed timing descriptor, or None if it is some other descriptor
  clock = d[0] | (d[1] << 8)
  if clock == 0:
    return None
  hactive = d[2] | ((d[4] & 0xF0) << 4)
  hblank = d[3] | ((d[4] & 0x0F) << 8)
  vactive = d[5] | ((d[7] & 0xF0) << 4)
  vblank = d[6] | ((d[7] & 0x0F) << 8)
  interlaced = bool(d[17] & 0x80)
  if hactive == 0 or vactive == 0:
    return None
  # The clock is in 10 kHz units; for interlaced modes the vertical values are
  # per field, so this is the field rate, which is what the kernel reports
  rate = round(clock * 10000 / ((hactive + hblank) * (vactive + vblank)))
  height = vactive * 2 if interlaced else vactive
  return _mode(hactive, height, rate, interlaced, preferred)


def _standardTiming(b1, b2, version):
  # A 2-byte standard timing, or None if the slot is unused
  if (b1 == 0x01 and b2 == 0x01) or b1 == 0x00:
    return None
  width = (b1 + 31) * 8
  aspect = b2 >> 6
  if aspect == 0:
    # 16:10 since EDID 1.3, 1:1 before
    height = width * 10 // 16 if version >= (1, 3) else width
  elif aspect == 1:
    height = width * 3 // 4
  elif aspect == 2:
    height = width * 4 // 5
  else:
    height = width * 9 // 16
  return _mode(width, height, (b2 & 0x3F) + 60, False)


def _cta(block):
  # Modes from a CTA-861 extension block: video data blocks and detailed timings
  modes = []
  dtdOffset = block[2]
  if 4 <= dtdOffset <= 127:
    i = 4
    while i < dtdOffset:
      tag = block[i] >> 5
      length = block[i] & 0x1F
      if tag == 2:
        for svd in block[i + 1:i + 1 + length]:
          # Codes 129-192 are codes 1-64 marked as native
          vic = svd - 128 if 129 <= svd <= 192 else svd
          if vic in _VIC:
            width, height, rate, interlaced = _VIC[vic]
            modes.append(_mode(width, height, rate, interlaced))
      i += 1 + length
    i = dtdOffset
    while i + 18 <= 127:
      mode = _detailedTiming(block[i:i + 18], False)
      if mode is None:
        break
      modes.append(mode)
      i += 18
  return modes


def parseEdid(edid):
  """Return the modes an EDID reports, preferred mode first. Empty if it is not a valid EDID."""
  if edid is None or len(edid) < 128 or edid[0:8] != _EDID_HEADER:
    return []
  version = (edid[18], edid[19])
  modes = []

  for i, mode in enumerate(_detailedTiming(edid[o:o + 18], False) for o in (54, 72, 90, 108)):
    if mode is not None:
      # The first detailed timing is the preferred mode
      mode['preferred'] = (i == 0)
      modes.append(mode)

  # Additional standard timings in display descriptors (tag 0xFA)
  for o in (54, 72, 90, 108):
    d = edid[o:o + 18]
    if d[0] == 0 and d[1] == 0 and d[3] == 0xFA:
      for j in range(5, 17, 2):
        mode = _standardTiming(d[j], d[j + 1], version)
        if mode is not None:
          modes.append(mode)

  for j in range(38, 54, 2):
    mode = _standardTiming(edid[j], edid[j + 1], version)
    if mode is not None:
      modes.append(mode)

  bits = (edid[35] << 16) | (edid[36] << 8) | edid[37]
  for j, timing in enumerate(_ESTABLISHED):
    if bits & (1 << (23 - j)):
      modes.append(_mode(*timing))

  for n in range(1, edid[126] + 1):
    block = edid[n * 128:(n + 1) * 128]
    if len(block) == 128 and block[0] == 0x02:
      modes.extend(_cta(block))

  return _unique(modes)


def parseSysfsModes(lines):
  """Modes from /sys/class/drm/*/modes, e.g. "1920x1080" or "1920x1080i". The first is preferred."""
  modes = []
  for i, line in enumerate(lines):
    m = re.match(r'^(\d+)x(\d+)(i?)$', line.strip())
    if m:
      modes.append(_mode(int(m.group(1)), int(m.group(2)), None, m.group(3) == 'i', i == 0))
  return _unique(modes)


def _unique(modes):
  result = []
  seen = set()
  for mode in modes:
    key = (mode['width'], mode['height'], mode['rate'], mode['interlaced'])
    if key in seen:
      if mode['preferred']:
        for other in result:
          if (other['width'], other['height'], other['rate'], other['interlaced']) == key:
            other['preferred'] = True
      continue
    seen.add(key)
    result.append(mode)
  return result


def modeString(mode):
  """WxH[@rate][i], the mode part of a setting value"""
  result = f"{mode['width']}x{mode['height']}"
  if mode['rate'] is not None:
    result += f"@{mode['rate']}"
  if mode['interlaced']:
    result += 'i'
  return result


def parseSettingMode(text):
  """Parse WxH[@rate][i] into a mode, or None"""
  m = _SETTING_MODE.match(text)
  if m is None:
    return None
  rate = int(m.group(3)) if m.group(3) else None
  return _mode(int(m.group(1)), int(m.group(2)), rate, m.group(4) == 'i')


def parseCmdlineMode(text):
  """Parse the mode part of video=<connector>:<mode> (without options).

  Returns a dict with 'mode' (a mode or None) and the flags to keep when the
  mode is replaced: 'bpp', 'margins' and 'force' (e, D or d). Returns None if
  the text is not a mode the kernel would parse this way (e.g. a named mode).
  """
  if _FLAGS_ONLY.match(text):
    return {'mode': None, 'bpp': None, 'margins': False, 'force': text}
  m = _CMDLINE_MODE.match(text)
  if m is None:
    return None
  rate = int(m.group(6)) if m.group(6) else None
  return {
    'mode': _mode(int(m.group(1)), int(m.group(2)), rate, m.group(7) == 'i'),
    'bpp': m.group(5),
    'margins': m.group(8) == 'm',
    'force': m.group(9),
  }


def cmdlineModeToSetting(text):
  """The setting's mode part for the mode part of a video= option: WxH[@rate][i], auto, or the text as is"""
  parsed = parseCmdlineMode(text)
  if parsed is None:
    return text
  if parsed['mode'] is None:
    return AUTO
  return modeString(parsed['mode'])


def settingToCmdlineMode(mode, existing):
  """The mode part of a video= option for a setting's mode part (a mode, or None for auto).

  Keeps the bpp, margins and force flags of the existing mode part. The M and
  R flags are dropped, since the new mode is one the display reports.
  """
  parsed = parseCmdlineMode(existing) if existing else None
  if parsed is None:
    parsed = {'bpp': None, 'margins': False, 'force': ''}
  if mode is None:
    return parsed['force']
  result = f"{mode['width']}x{mode['height']}"
  if parsed['bpp']:
    result += f"-{parsed['bpp']}"
  if mode['rate'] is not None:
    result += f"@{mode['rate']}"
  if mode['interlaced']:
    result += 'i'
  if parsed['margins']:
    result += 'm'
  return result + parsed['force']


def splitValue(value):
  """Split a setting value into (connector, mode part). The connector is None for a bare mode part."""
  if value is None:
    return (None, AUTO)
  value = str(value).strip()
  if ':' in value:
    connector, mode = value.split(':', 1)
    return (connector, mode)
  return (None, value)


def normalizeValue(value):
  """The canonical form of a setting value, or None if it is not one"""
  connector, mode = splitValue(value)
  if connector is not None and not re.match(r'^[A-Za-z0-9-]+$', connector):
    return None
  if mode == AUTO:
    pass
  else:
    parsed = parseSettingMode(mode)
    if parsed is None:
      return None
    mode = modeString(parsed)
  return mode if connector is None else f'{connector}:{mode}'


def _read(name, binary=False):
  try:
    with open(name, 'rb' if binary else 'r') as f:
      return f.read()
  except OSError:
    return None


def connectors():
  """The connected connectors, as a list of {'name', 'edid', 'modes'}"""
  result = []
  seen = set()
  try:
    entries = sorted(os.listdir(DRM_ROOT))
  except OSError:
    return result
  for entry in entries:
    m = re.match(r'^card\d+-(.+)$', entry)
    if m is None or m.group(1) in seen:
      continue
    base = os.path.join(DRM_ROOT, entry)
    status = _read(os.path.join(base, 'status'))
    if status is None or status.strip() != 'connected':
      continue
    seen.add(m.group(1))
    sysfs = _read(os.path.join(base, 'modes')) or ''
    result.append({
      'name': m.group(1),
      'edid': _read(os.path.join(base, 'edid'), binary=True),
      'modes': sysfs.splitlines(),
    })
  return result


def connectorModes(connector):
  """The modes a connector offers: the EDID's, plus any only the kernel lists"""
  modes = parseEdid(connector['edid'])
  sysfs = parseSysfsModes(connector['modes'])
  if not modes:
    return sysfs
  sizes = set((m['width'], m['height'], m['interlaced']) for m in modes)
  for mode in sysfs:
    if (mode['width'], mode['height'], mode['interlaced']) not in sizes:
      mode['preferred'] = False
      modes.append(mode)
  return modes


def sortModes(modes):
  return sorted(modes, key=lambda m: (m['width'] * m['height'], m['rate'] or 0, not m['interlaced']), reverse=True)


def entry(connector, mode, label=None, multiple=False):
  """A mode as the settings page lists it"""
  if mode is None:
    value = f'{connector}:{AUTO}'
    text = label or 'Automatic (display\'s preferred mode)'
    result = {'mode': connector, 'code': AUTO, 'width': None, 'height': None, 'rate': None, 'scan': ''}
  else:
    code = modeString(mode)
    value = f'{connector}:{code}'
    scan = 'i' if mode['interlaced'] else ''
    text = label or f"{mode['width']}x{mode['height']}{scan}"
    if mode['rate'] is not None and label is None:
      text += f" ({mode['rate']}Hz)"
    if mode['preferred'] and label is None:
      text += ', preferred'
    result = {'mode': connector, 'code': code, 'width': mode['width'], 'height': mode['height'], 'rate': mode['rate'], 'scan': scan}
  if multiple:
    text = f'{connector}: {text}'
  result['value'] = value
  result['label'] = text
  return result


def isAvailable(value, entries):
  value = normalizeValue(value)
  return value is not None and any(e['value'] == value for e in entries)
