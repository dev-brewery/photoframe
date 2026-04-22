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
from threading import Thread
import select
import subprocess
import os
import socket
import logging
import atexit

class shutdown(Thread):
	@staticmethod
	def detect_default_pin():
		"""Auto-detect GPIO pin based on TCS34725 color sensor presence.

		Returns GPIO 26 if sensor detected (conflicts with GPIO 3's I2C),
		otherwise GPIO 3 (allows halt-then-restart via button).
		"""
		try:
			import smbus
			bus = smbus.SMBus(1)
			try:
				bus.write_byte(0x29, 0x80 | 0x12)
				device_id = bus.read_byte(0x29)
				if device_id == 0x44:
					logging.info('TCS34725 detected, using GPIO 26 for shutdown')
					return 26
			finally:
				bus.close()
		except Exception:
			pass
		logging.info('No color sensor detected, using GPIO 3 for shutdown')
		return 3

	def __init__(self, usePIN=26):
		Thread.__init__(self)
		self.daemon = True
		self.gpio = usePIN
		self.void = open(os.devnull, 'wb')
		atexit.register(self._cleanup)
		self.client, self.server = socket.socketpair()
		self.start()

	def _cleanup(self):
		if hasattr(self, 'void') and self.void:
			self.void.close()

	def stopmonitor(self):
		self.client.close()

	def run(self):
		logging.info(f'GPIO shutdown can be triggered by GPIO {self.gpio}')
		poller = select.poll()
		try:
			with open('/sys/class/gpio/export', 'wb') as f:
				f.write(str(self.gpio).encode('utf-8'))
		except:
			# Usually it means we ran this before
			pass
		try:
			with open(f'/sys/class/gpio/gpio{self.gpio}/direction', 'wb') as f:
				f.write(b'in')
		except:
			logging.warn('Either no GPIO subsystem or no access')
			return
		with open(f'/sys/class/gpio/gpio{self.gpio}/edge', 'wb') as f:
			f.write(b'both')
		with open(f'/sys/class/gpio/gpio{self.gpio}/active_low', 'wb') as f:
			f.write(b'1')
		with open(f'/sys/class/gpio/gpio{self.gpio}/value', 'rb') as f:
			f.read()
			poller.register(f, select.POLLPRI)
			poller.register(self.server, select.POLLHUP)
			i = poller.poll(None)
			for (fd, event) in i:
				if f.fileno() == fd:
					subprocess.call(['/sbin/poweroff'], stderr=self.void);
					logging.debug('Shutdown GPIO triggered')
				elif self.server.fileno() == fd:
					logging.debug('Quitting shutdown manager')
