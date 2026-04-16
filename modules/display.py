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
import subprocess
import logging
import time
import re
import json
import atexit
from pathlib import Path

import modules.debug as debug
from modules.sysconfig import sysconfig
from modules.helper import helper

# Determine rgb565 path relative to this module (works from /root/photoframe or /home/pi/photoframe)
# Supports both 32-bit (armhf) and 64-bit (arm64) builds
def _find_rgb565():
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rgb565')
    candidates = ['rgb565', 'rgb565_arm64', 'rgb565_armhf']
    for name in candidates:
        path = os.path.join(base_dir, name)
        if os.path.exists(path):
            try:
                # Test if binary actually runs on this architecture
                result = subprocess.run([path], stdin=subprocess.DEVNULL, capture_output=True, timeout=2)
                logging.debug(f'rgb565 binary {path} is usable')
                return path
            except (OSError, subprocess.TimeoutExpired):
                continue
    logging.warning('No working rgb565 binary found, 16-bit displays may not work')
    return os.path.join(base_dir, 'rgb565')  # Fallback to default name

_RGB565_PATH = _find_rgb565()

class display:
    def __init__(self, use_emulator=False, emulate_width=1280, emulate_height=720):
        self.void = open(os.devnull, 'wb')
        atexit.register(self._cleanup)
        self.params = None
        self.special = None
        self.emulate = use_emulator
        self.emulate_width = emulate_width
        self.emulate_height = emulate_height
        self.rotated = sysconfig.isDisplayRotated()
        self.xoffset = 0
        self.yoffset = 0
        self.url = None
        if self.emulate:
            logging.info('Using framebuffer emulation')
        self.lastMessage = None
        
        # Initialize display configuration
        self.display_config = self._get_default_config()
        
        # Check if tvservice is available for backward compatibility
        self.has_tvservice = self._determine_display_method()
        if not self.has_tvservice:
            logging.info('tvservice not available, using modern display detection methods')

    def _cleanup(self):
        if hasattr(self, 'void') and self.void:
            self.void.close()

    def _get_default_config(self):
        """Get default display configuration"""
        return {
            'force_modern': False,          # Force modern methods
            'force_legacy': False,          # Force tvservice
            'detection_timeout': 10,        # Detection timeout seconds
            'fallback_resolution': '1280x720',  # Safe fallback
            'retry_attempts': 3,            # Failed detection retries
            'validate_on_startup': True     # Validate display on service start
        }

    def _determine_display_method(self):
        """Determine which display method to use based on config and availability"""
        # Check configuration overrides first
        if self.display_config.get('force_modern'):
            logging.info('Configuration forces modern display detection')
            return False
        if self.display_config.get('force_legacy'):
            logging.info('Configuration forces legacy tvservice detection')
            return self._check_tvservice_available()

        # Auto-detect based on availability
        return self._check_tvservice_available()

    def get_display_diagnostics(self):
        """Comprehensive display system diagnostics"""
        health = self._validate_display_health()
        fb_info = self._get_framebuffer_info()

        diagnostics = {
            'detection_method': 'tvservice' if self.has_tvservice else 'modern',
            'tvservice_available': self._check_tvservice_available(),
            'framebuffer_accessible': health.get('framebuffer_accessible', False),
            'current_resolution': f"{fb_info['width']}x{fb_info['height']}" if fb_info else 'unknown',
            'color_depth': fb_info.get('depth', 'unknown') if fb_info else 'unknown',
            'supported_modes': len(self.available()) if hasattr(self, 'available') else 0,
            'health_status': health,
            'configuration': self.display_config,
            'last_error': None  # Could be expanded to track errors
        }

        return diagnostics

    def setConfigPage(self, url):
        self.url = url

    def setConfiguration(self, tvservice_params, special=None):
        self.enabled = True

        # Erase old picture
        if self.params is not None:
            self.clear()

        if self.emulate:
            self.width = self.emulate_width
            self.height = self.emulate_height
            self.depth = 32
            self.reverse = False
            self.format = 'rgba'
            self.params = None
            self.special = None
            return (self.width, self.height, '')

        result = display.validate(tvservice_params, special)
        if result is None:
            logging.error('Unable to find a valid display mode, will default to 1280x720')
            # TODO: THis is less than ideal, maybe we should fetch resolution from fbset instead?
            #       but then we should also avoid touching the display since it will cause issues.
            self.enabled = False
            self.params = None
            self.special = None
            return (1280, 720, '')

        self.width = result['width']
        self.height = result['height']
        self.pwidth = self.width
        self.pheight = self.height

        if self.rotated:
            # Calculate offset for X, must be even dividable with 16
            self.xoffset = (16 - (self.height % 16)) % 16
            self.width = self.pheight
            self.height = self.pwidth

        self.depth = result['depth']
        self.reverse = result['reverse']
        self.params = result['tvservice']
        if self.reverse:
            self.format = 'bgr'
        else:
            self.format = 'rgb'
        if self.depth == 32:
            self.format += 'a'

        return (self.width, self.height, self.params)

    def getDevice(self):
        if self.params and self.params.split(' ')[0] == 'INTERNAL':
            device = f'/dev/fb{self.params.split(" ")[1]}'
            if os.path.exists(device):
                return device
        return '/dev/fb0'

    def isHDMI(self):
        return self.getDevice() == '/dev/fb0' and not display._isDPI()

    def get(self):
        if self.enabled:
            args = [
                'convert',
                '-depth',
                '8',
                '-size',
                f'{self.width+self.xoffset}x{self.height+self.yoffset}',
                f'{self.format}:-',
                'jpg:-'
            ]
        else:
            args = [
                'convert',
                '-size',
                '640x360',
                '-background',
                'black',
                '-fill',
                'white',
                '-gravity',
                'center',
                '-weight',
                '700',
                '-pointsize',
                '32',
                'label:Display off',
                '-depth',
                '8',
                'jpg:-'
            ]

        if not self.enabled:
            result = debug.subprocess_check_output(args, stderr=self.void)
        elif self.depth in [24, 32]:
            device = self.getDevice()
            if self.emulate:
                device = '/tmp/fb.bin'
            with open(device, 'rb') as fb:
                pip = subprocess.Popen(args, stdin=fb, stdout=subprocess.PIPE, stderr=self.void)
                result = pip.communicate()[0]
        elif self.depth == 16:
            src = None
            pip = None
            try:
                with open(self.getDevice(), 'rb') as fb:
                    src = subprocess.Popen([_RGB565_PATH, 'reverse'], stdout=subprocess.PIPE, stdin=fb, stderr=self.void)
                    pip = subprocess.Popen(args, stdin=src.stdout, stdout=subprocess.PIPE)
                    src.stdout.close()
                    result = pip.communicate()[0]
            finally:
                if src:
                    src.terminate()
                    src.wait()
                if pip:
                    pip.terminate()
                    pip.wait()
        else:
            logging.error('Do not know how to grab this kind of framebuffer')
        return (result, 'image/jpeg')

    def _to_display(self, arguments):
        device = self.getDevice()
        if self.emulate:
            device = '/tmp/fb.bin'
            self.depth = 32

        if self.depth in [24, 32]:
            with open(device, 'wb') as f:
                debug.subprocess_call(arguments, stdout=f, stderr=self.void)
        elif self.depth == 16:  # Typically RGB565
            # For some odd reason, cannot pipe the output directly to the framebuffer, use temp file
            src = None
            pip = None
            try:
                with open(device, 'wb') as fb:
                    src = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=self.void)
                    pip = subprocess.Popen([_RGB565_PATH], stdin=src.stdout, stdout=fb)
                    src.stdout.close()
                    pip.communicate()
            finally:
                if src:
                    src.terminate()
                    src.wait()
                if pip:
                    pip.terminate()
                    pip.wait()
        else:
            logging.error(f'Do not know how to render this, depth is {self.depth}')

        self.lastMessage = None

    def message(self, message, showConfig=True):
        if not self.enabled:
            logging.debug('Don\'t bother, display is off')
            return

        url = 'caption:'
        if helper.getDeviceIp() is not None and showConfig:
            url = f'caption:Configuration available at http://{helper.getDeviceIp()}:7777'

        args = [
            'convert',
            '-size',
            f'{self.width}x{self.height}',
            '-background',
            'black',
            '-fill',
            'white',
            '-gravity',
            'center',
            '-weight',
            '700',
            '-pointsize',
            '32',
            f'caption:{message}',
            '-background',
            'none',
            '-gravity',
            'south',
            '-fill',
            '#666666',
            url,
            '-flatten',
            '-extent',
            f'{self.width + self.xoffset}x{self.height + self.yoffset}+{self.xoffset}+{self.yoffset}',
            '-depth',
            '8',
            f'{self.format}:-'
        ]

        if self.lastMessage != message:
            self._to_display(args)
            self.lastMessage = message

    def image(self, filename):
        if not self.enabled:
            logging.debug('Don\'t bother, display is off')
            return

        logging.debug('Showing image to user')
        args = [
            'convert',
            filename + '[0]',
            '-background',
            'black',
            '-gravity',
            'center',
            '-extent',
            f'{self.width + self.xoffset}x{self.height + self.yoffset}+{self.xoffset}+{self.yoffset}',
            '-depth',
            '8',
            f'{self.format}:-'
        ]
        self._to_display(args)

    def enable(self, enable, force=False):
        if enable == self.enabled and not force:
            return

        # Do not do things if we don't know how to display
        if self.params is None:
            logging.error('Cannot enable display: display parameters not initialized (setConfiguration failed)')
            return
            
        logging.info(f'Display enable called: enable={enable}, has_tvservice={self.has_tvservice}, params={self.params}')

        if enable:
            if self.has_tvservice:
                # Use traditional tvservice method
                if self.special:
                    debug.subprocess_call(['tvservice', '-p', self.special], stderr=self.void)
                else:
                    debug.subprocess_call(['tvservice', '-p', self.params], stderr=self.void)
                time.sleep(1)
                # Traditional framebuffer configuration
                debug.subprocess_call(['fbset', '-depth', str(self.depth)], stderr=self.void)
                debug.subprocess_call(['fbset', '-g', str(self.width), str(self.height), str(self.width), str(self.height), str(self.depth)], stderr=self.void)
                debug.subprocess_call(['fbset', '-accel', 'true'], stderr=self.void)
                debug.subprocess_call(['fbset', '-move', 'up'], stderr=self.void)
                debug.subprocess_call(['fbset', '-move', 'down'], stderr=self.void)
            else:
                # Use modern fallback - take control of display properly
                self._modern_enable(True)
        else:
            if self.has_tvservice:
                debug.subprocess_call(['tvservice', '-o'], stderr=self.void)
            else:
                # Use modern fallback disable method  
                self._modern_enable(False)

        self.enabled = enable

    def isEnabled(self):
        return self.enabled

    def clear(self):
        if not self.enabled:
            return

        args = [
            'convert',
            '-size',
            f'{self.width + self.xoffset}x{self.height + self.yoffset}',
            'xc:black',
            '-depth',
            '8',
            f'{self.format}:-'
        ]
        self._to_display(args)

    @staticmethod
    def _isDPI():
        try:
            with open('/proc/device-tree/soc/video@7e900000/status', 'r') as f:
                return f.read().strip() == 'okay'
        except:
            return False

    @staticmethod
    def _internaldisplay():
        try:
            with open('/proc/device-tree/soc/video@7e900000/status', 'r') as f:
                return f.read().strip() == 'okay'
        except:
            return False

    def current(self):
        if self.params is None:
            return None

        result = {}
        result['width'] = self.pwidth
        result['height'] = self.pheight
        result['depth'] = self.depth
        result['tvservice'] = self.params
        result['special'] = self.special
        result['rotated'] = self.rotated
        return result

    @staticmethod
    def available():
        """Get available display modes using hybrid detection (tvservice or modern fallback)"""
        result = []
        
        # Try tvservice first (backward compatibility)
        tvservice_available = False
        try:
            subprocess.run(['tvservice', '--help'], capture_output=True, timeout=5, check=False)
            tvservice_available = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        if tvservice_available:
            # Use traditional tvservice method
            try:
                output = subprocess.check_output(['tvservice', '-m', 'CEA'], stderr=subprocess.DEVNULL).decode('utf-8')
                for line in output.split('\n'):
                    if line.startswith('mode '):
                        result.append(line[5:])
            except:
                pass

            try:
                output = subprocess.check_output(['tvservice', '-m', 'DMT'], stderr=subprocess.DEVNULL).decode('utf-8')
                for line in output.split('\n'):
                    if line.startswith('mode '):
                        result.append(line[5:])
            except:
                pass
        else:
            # Use modern fallback method
            logging.info('tvservice unavailable, using modern display detection')
            # Create a temporary display instance to access modern methods
            temp_display = display()
            result = temp_display._modern_available()
            
        return result

    @staticmethod
    def validate(tvservice, special):
        """Validate display mode using hybrid detection (tvservice or modern fallback)"""
        # Check if tvservice is available
        tvservice_available = False
        try:
            subprocess.run(['tvservice', '--help'], capture_output=True, timeout=5, check=False)
            tvservice_available = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        if tvservice_available:
            # Use traditional tvservice validation
            if special:
                try:
                    output = subprocess.check_output(['tvservice', '-s'], stderr=subprocess.DEVNULL).decode('utf-8')
                    if output.find(special) != -1:
                        return {
                            'width': 1280,
                            'height': 720,
                            'depth': 32,
                            'reverse': False,
                            'tvservice': special
                        }
                except:
                    pass

            if not tvservice:
                return None

            try:
                output = subprocess.check_output(['tvservice', '-s'], stderr=subprocess.DEVNULL).decode('utf-8')
                if output.find(tvservice) == -1:
                    return None
            except:
                return None

            try:
                output = subprocess.check_output(['tvservice', '-v', tvservice], stderr=subprocess.DEVNULL).decode('utf-8')
                m = re.search(r'(\d+)x(\d+)', output)
                if m:
                    width = int(m.group(1))
                    height = int(m.group(2))
                    depth = 32
                    reverse = False
                    return {
                        'width': width,
                        'height': height,
                        'depth': depth,
                        'reverse': reverse,
                        'tvservice': tvservice
                    }
            except:
                pass
        else:
            # Use modern validation fallback
            logging.info('tvservice unavailable, using modern display validation')
            temp_display = display()
            return temp_display._modern_validate(tvservice, special)

        return None

    def _check_tvservice_available(self):
        """Check if tvservice command is available (backward compatibility)"""
        try:
            subprocess.run(['tvservice', '--help'], capture_output=True, timeout=5, check=False)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _get_framebuffer_info(self):
        """Get current framebuffer information with comprehensive validation"""
        try:
            # Check framebuffer device accessibility
            fb_device = '/dev/fb0'
            if not os.path.exists(fb_device):
                logging.warning('Primary framebuffer device /dev/fb0 not found')
                return None
                
            if not os.access(fb_device, os.R_OK | os.W_OK):
                logging.warning('Insufficient permissions for framebuffer access')
                return None
            
            # Get framebuffer info using fbset
            output = subprocess.check_output(['fbset', '-s'], stderr=subprocess.DEVNULL, timeout=10).decode('utf-8')
            
            # Parse fbset output
            width = height = depth = None
            for line in output.split('\n'):
                if 'geometry' in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        width = int(parts[1])
                        height = int(parts[2]) 
                        depth = int(parts[5])
                        break
            
            if width and height and depth:
                # Validate reasonable display dimensions
                if width < 100 or height < 100 or width > 8192 or height > 8192:
                    logging.warning(f'Suspicious display dimensions: {width}x{height}')
                    return None
                if depth not in [16, 24, 32]:
                    logging.warning(f'Unsupported color depth: {depth}')
                    return None
                    
                logging.info(f'Detected framebuffer: {width}x{height}@{depth}bit')
                return {
                    'width': width,
                    'height': height,
                    'depth': depth
                }
        except subprocess.TimeoutExpired:
            logging.warning('fbset command timed out')
        except Exception as e:
            logging.warning(f'Failed to get framebuffer info: {e}')
        
        return None

    def _detect_display_with_fallbacks(self):
        """Multi-layer fallback detection strategy"""
        detection_methods = [
            ('framebuffer', self._framebuffer_detection),
            ('safe_defaults', self._safe_defaults_detection)
        ]
        
        for method_name, method in detection_methods:
            try:
                logging.debug(f'Trying display detection method: {method_name}')
                result = method()
                if self._validate_detection_result(result):
                    logging.info(f'Display detection successful using: {method_name}')
                    return result
            except Exception as e:
                logging.warning(f'Detection method {method_name} failed: {e}')
                continue
        
        logging.error('All display detection methods failed')
        raise Exception('All display detection methods failed')

    def _framebuffer_detection(self):
        """Primary modern detection method using framebuffer"""
        fb_info = self._get_framebuffer_info()
        modes = []
        
        if fb_info:
            # Current detected mode
            mode_str = f"1: {fb_info['width']}x{fb_info['height']}@60Hz 16:9"
            modes.append(mode_str)
            logging.info(f'Added detected framebuffer mode: {mode_str}')
        
        # Always add common fallback modes 
        common_modes = [
            "82: 1920x1080@60Hz 16:9",
            "85: 1280x720@60Hz 16:9", 
            "87: 800x480@60Hz 5:3",
            "16: 1024x768@60Hz 4:3",
            "9: 800x600@60Hz 4:3"
        ]
        
        # Filter out duplicates if we detected the current resolution
        current_res = f"{fb_info['width']}x{fb_info['height']}" if fb_info else ""
        for mode in common_modes:
            mode_res = mode.split('@')[0].split(': ')[1]
            if mode_res != current_res:
                modes.append(mode)
        
        if not modes:
            logging.warning('No display modes detected, using emergency defaults')
            return None
            
        return modes

    def _safe_defaults_detection(self):
        """Ultimate fallback with safe default modes"""
        logging.warning('Using safe default display modes')
        return [
            "85: 1280x720@60Hz 16:9",
            "87: 800x480@60Hz 5:3",
            "16: 1024x768@60Hz 4:3"
        ]

    def _validate_detection_result(self, result):
        """Validate that detection result is usable"""
        if not result or not isinstance(result, list):
            return False
        if len(result) == 0:
            return False
        # Check that modes follow expected format
        for mode in result:
            if not isinstance(mode, str) or ':' not in mode:
                return False
        return True

    def _modern_available(self):
        """Modern fallback for display mode detection when tvservice unavailable"""
        try:
            return self._detect_display_with_fallbacks()
        except Exception as e:
            logging.error(f'All modern detection methods failed: {e}')
            # Final emergency fallback
            return ["85: 1280x720@60Hz 16:9"]

    def _validate_display_health(self):
        """Comprehensive display system health validation"""
        health_status = {
            'framebuffer_accessible': False,
            'resolution_valid': False,
            'color_depth_supported': False,
            'device_writeable': False,
            'errors': []
        }
        
        try:
            # Check framebuffer device existence and permissions
            fb_device = '/dev/fb0'
            if not os.path.exists(fb_device):
                health_status['errors'].append('Framebuffer device not found')
                return health_status
                
            if not os.access(fb_device, os.R_OK | os.W_OK):
                health_status['errors'].append('Insufficient framebuffer permissions')
                return health_status
                
            health_status['framebuffer_accessible'] = True
            health_status['device_writeable'] = True
            
            # Validate current resolution and settings
            fb_info = self._get_framebuffer_info()
            if fb_info:
                if fb_info['width'] >= 100 and fb_info['height'] >= 100:
                    health_status['resolution_valid'] = True
                if fb_info['depth'] in [16, 24, 32]:
                    health_status['color_depth_supported'] = True
            else:
                health_status['errors'].append('Could not read framebuffer configuration')
                
        except Exception as e:
            health_status['errors'].append(f'Health check failed: {str(e)}')
            
        return health_status

    def _modern_validate(self, requested_mode, special):
        """Modern fallback for display validation with health checking"""
        # First perform health validation
        health = self._validate_display_health()
        if health['errors']:
            logging.warning(f'Display health issues detected: {health["errors"]}')
            
        if special:
            # For special modes, return default safe values
            return {
                'width': 1280,
                'height': 720,
                'depth': 32,
                'reverse': False,
                'tvservice': special
            }
        
        # Get current framebuffer info with health validation
        fb_info = self._get_framebuffer_info()
        if fb_info and health['framebuffer_accessible']:
            tvservice_str = f"{fb_info['width']}x{fb_info['height']}-{fb_info['depth']}@60"
            logging.info(f'Modern validation using detected framebuffer: {tvservice_str}')
            return {
                'width': fb_info['width'],
                'height': fb_info['height'],
                'depth': fb_info['depth'],
                'reverse': False,  # Assume RGB for modern HDMI displays
                'tvservice': tvservice_str
            }
        
        # Graceful degradation with safe defaults - NEVER return None
        logging.warning('Framebuffer detection failed, using safe default display configuration')
        return {
            'width': 800,
            'height': 480,  # Good default for small displays
            'depth': 16,    # Conservative depth
            'reverse': False,
            'tvservice': '800x480-16@60'
        }

    def _modern_enable(self, enable):
        """Modern fallback for display control when tvservice unavailable"""
        try:
            if enable:
                logging.info('Modern display enable: taking control from desktop environment')
                
                # Stop the display manager (Bookworm desktop ships lightdm; harmless no-op on Lite)
                debug.subprocess_call(['sudo', 'systemctl', 'stop', 'lightdm.service'], stderr=self.void)

                # Kill any running desktop environment processes that might interfere
                debug.subprocess_call(['sudo', 'pkill', '-f', 'lxsession'], stderr=self.void)
                debug.subprocess_call(['sudo', 'pkill', '-f', 'openbox'], stderr=self.void)
                debug.subprocess_call(['sudo', 'pkill', '-f', 'pcmanfm'], stderr=self.void)
                
                # Switch to console tty1 to take control from X11/desktop
                debug.subprocess_call(['sudo', 'chvt', '1'], stderr=self.void)
                time.sleep(1)  # Give time for console switch
                
                # Disable console cursor and clear screen
                debug.subprocess_call(['sh', '-c', 'echo 0 > /sys/class/graphics/fbcon/cursor_blink'], stderr=self.void)
                debug.subprocess_call(['clear'], stderr=self.void)
                
                # Configure framebuffer geometry and depth
                debug.subprocess_call(['fbset', '-depth', str(self.depth)], stderr=self.void)
                debug.subprocess_call(['fbset', '-g', str(self.width), str(self.height), 
                                     str(self.width), str(self.height), str(self.depth)], stderr=self.void)
                debug.subprocess_call(['fbset', '-accel', 'true'], stderr=self.void)
                debug.subprocess_call(['fbset', '-move', 'up'], stderr=self.void)
                debug.subprocess_call(['fbset', '-move', 'down'], stderr=self.void)
                
                # Clear the framebuffer to black
                debug.subprocess_call(['sh', '-c', f'dd if=/dev/zero of=/dev/fb0 bs={self.width*self.height*4} count=1'], stderr=self.void)
                
                logging.info('Modern display control: framebuffer takeover complete')
            else:
                logging.info('Modern display disable: blanking framebuffer')
                # Blank the framebuffer to turn off display
                try:
                    with open('/sys/class/graphics/fb0/blank', 'w') as f:
                        f.write('1')  # Blank display
                except:
                    logging.debug('Could not blank framebuffer via sysfs')
        except Exception as e:
            logging.debug(f'Modern display control failed: {e}')
