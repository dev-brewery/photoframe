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

from .baseroute import BaseRoute

class RouteControl(BaseRoute):
  def setupex(self, slideshow, timekeeper):
    self.slideshow = slideshow
    self.timekeeper = timekeeper

    self.addUrl('/control/<cmd>')

  def handle(self, app, cmd):
    if cmd == 'screenon':
      self.timekeeper.setManualPower(True)
      return self.jsonify({'screen': 'on', 'success': True})
    elif cmd == 'screenoff':
      self.timekeeper.setManualPower(False)
      return self.jsonify({'screen': 'off', 'success': True})

    self.slideshow.createEvent(cmd)
    return self.jsonify({'control': True})

