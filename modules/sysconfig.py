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
import os
import json
import re
import subprocess
from pathlib import Path

from modules.path import path
import logging

class sysconfig:
  @staticmethod
  def _getConfigFileState(key):
    if os.path.exists(path.CONFIG_TXT):
      with open(path.CONFIG_TXT, 'r') as f:
        for line in f:
          clean = line.strip()
          if clean == '':
            continue
          if clean.startswith(f'{key}='):
            _, value = clean.split('=', 1)
            return value
    return None

  @staticmethod
  def _changeConfigFile(key, value):
    configline = f'{key}={value}\n'
    found = False
    if os.path.exists(path.CONFIG_TXT):
      with open(path.CONFIG_TXT, 'r') as ifile:
        with open(f'{path.CONFIG_TXT}.new', 'w') as ofile:
          for line in ifile:
            clean = line.strip()
            if clean.startswith(f'{key}='):
              found = True
              line = configline
            ofile.write(line)
          if not found:
            ofile.write(configline)
      try:
        os.rename(path.CONFIG_TXT, f'{path.CONFIG_TXT}.old')
        os.rename(f'{path.CONFIG_TXT}.new', path.CONFIG_TXT)
        # Keep the first version of the config.txt just-in-case
        if os.path.exists(f'{path.CONFIG_TXT}.original'):
          os.unlink(f'{path.CONFIG_TXT}.old')
        else:
          os.rename(f'{path.CONFIG_TXT}.old', f'{path.CONFIG_TXT}.original')
        return True
      except Exception as e:
        logging.exception('Failed to activate new config.txt, you may need to restore the config.txt')

  @staticmethod
  def usesKMS():
    # True with the KMS driver (vc4-kms-v3d) or the fake-KMS driver (vc4-fkms-v3d).
    # Under KMS display_rotate has no effect on screen (#109); under fake KMS the
    # framebuffer keeps the display's unrotated size. Either way photoframe must not
    # swap width and height for display_rotate.
    if os.path.exists(path.CONFIG_TXT):
      with open(path.CONFIG_TXT, 'r') as f:
        for line in f:
          clean = line.strip()
          if clean.startswith('dtoverlay=vc4-kms-v3d') or clean.startswith('dtoverlay=vc4-fkms-v3d'):
            return True
    return False

  @staticmethod
  def _displayRotateQuarterTurns():
    # display_rotate may be written in hex with flip bits (e.g. 0x10002);
    # the low two bits are the rotation in quarter turns
    state = sysconfig._getConfigFileState('display_rotate')
    if state is None:
      return 0
    state = state.strip()
    try:
      value = int(state, 16) if state.lower().startswith('0x') else int(state)
    except ValueError:
      value = -1
    if value < 0:
      logging.warning(f'Ignoring display_rotate={state} in {path.CONFIG_TXT}, it is not a valid value')
      return 0
    return value & 3

  @staticmethod
  def isDisplayRotated():
    return sysconfig._displayRotateQuarterTurns() in (1, 3)

  @staticmethod
  def getDisplayOrientation():
    return sysconfig._displayRotateQuarterTurns() * 90

  @staticmethod
  def setDisplayOverscan(enable):
    if enable:
      return sysconfig._changeConfigFile('disable_overscan', '0')
    else:
      return sysconfig._changeConfigFile('disable_overscan', '1')

  @staticmethod
  def isDisplayOverscan():
    state = sysconfig._getConfigFileState('disable_overscan')
    if state is not None:
      return state == '0'
    return True # Typically true for RPi

  @staticmethod
  def setDisplayOrientation(deg):
    return sysconfig._changeConfigFile('display_rotate', str(int(deg/90)))

  @staticmethod
  def _app_opt_load():
    if os.path.exists(path.OPTIONSFILE):
      lines = {}
      with open(path.OPTIONSFILE, 'r') as f:
        for line in f:
          key, value = line.strip().split('=', 1)
          lines[key.strip()] = value.strip()
      return lines
    return None

  @staticmethod
  def _app_opt_save(lines):
    with open(path.OPTIONSFILE, 'w') as f:
      for key in lines:
        f.write(f'{key}={lines[key]}\n')

  @staticmethod
  def setOption(key, value):
    lines = sysconfig._app_opt_load()
    if lines is None:
      lines = {}
    lines[key] = value
    sysconfig._app_opt_save(lines)

  @staticmethod
  def getOption(key):
    lines = sysconfig._app_opt_load()
    if lines is None:
      lines = {}
    if key in lines:
      return lines[key]
    return None

  @staticmethod
  def removeOption(key):
    lines = sysconfig._app_opt_load()
    if lines is None:
      return
    lines.pop(key, False)
    sysconfig._app_opt_save(lines)

  @staticmethod
  def getHTTPAuth():
    user = None
    userfiles = ['/boot/http-auth.json', '/boot/firmware/http-auth.json', f'{path.CONFIGFOLDER}/http-auth.json']
    for userfile in userfiles:
      if os.path.exists(userfile):
        logging.debug(f'Found "{userfile}", loading the data')
        try:
          with open(userfile, 'r') as f:
            user = json.load(f)
            if 'user' not in user or 'password' not in user:
              logging.warning(f'"{userfile}" doesn\'t contain a user and password key')
              user = None
            else:
              break
        except Exception as e:
          logging.exception(f'Unable to load JSON from "{userfile}"')
          user = None
    return user

  @staticmethod
  def setHostname(name):
    # First, make sure it's legal
    name = re.sub(' ', '-', name.strip())
    name = re.sub(r'[^a-zA-Z0-9\-]', '', name).strip()
    if name == '' or len(name) > 63:
      return False

    # Next, let's edit the relevant files....
    with open('/etc/hostname', 'w') as f:
      f.write(f'{name}\n')

    lines = []
    with open('/etc/hosts', 'r') as f:
      for line in f:
        line = line.strip()
        if line.startswith('127.0.1.1'):
          line = f'127.0.1.1\t{name}'
        lines.append(line)
    with open('/etc/hosts.new', 'w') as f:
      for line in lines:
        f.write(f'{line}\n')

    try:
      os.rename('/etc/hosts', '/etc/hosts.old')
      os.rename('/etc/hosts.new', '/etc/hosts')
      # Keep the first version of the config.txt just-in-case
      os.unlink('/etc/hosts.old')

      # also, run hostname with the new name
      with open(os.devnull, 'wb') as void:
        subprocess.check_call(['/bin/hostname', name], stderr=void)

      # Final step, restart avahi (so it knows the correct hostname)
      try:
        with open(os.devnull, 'wb') as void:
          subprocess.check_call(['/usr/sbin/service', 'avahi-daemon', 'restart'], stderr=void)
      except subprocess.CalledProcessError:
        logging.exception('Couldnt restart avahi, not a deal breaker')
      return True
    except Exception as e:
      logging.exception('Failed to activate new hostname, you should probably reboot to restore')
    return False

  @staticmethod
  def getHostname():
    with open('/etc/hostname', 'r') as f:
      return f.read().strip()
