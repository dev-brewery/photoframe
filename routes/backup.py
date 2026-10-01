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

import logging
import os
import tarfile
import tempfile
import shutil
from datetime import datetime

from flask import send_file
from werkzeug.utils import secure_filename
from .baseroute import BaseRoute
from modules.path import path


class RouteBackup(BaseRoute):
    def setupex(self, settingsmgr, slideshow):
        self.settingsmgr = settingsmgr
        self.slideshow = slideshow

        self.addUrl('/backup/export')
        self.addUrl('/backup/import').clearMethods().addMethod('POST')

    def handle(self, app):
        if self.getRequest().method == 'GET':
            return self._handleExport()
        elif self.getRequest().method == 'POST':
            return self._handleImport()
        self.setAbort(405)

    def _handleExport(self):
        """Create and return a tar.gz of the config folder."""
        config_folder = path.CONFIGFOLDER

        if not config_folder.exists():
            return self.jsonify({'status': False, 'error': 'Config folder does not exist'})

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = f'photoframe-config-{timestamp}.tar.gz'

        try:
            fd, tmppath = tempfile.mkstemp(suffix='.tar.gz')
            os.close(fd)

            with tarfile.open(tmppath, 'w:gz') as tar:
                tar.add(str(config_folder), arcname='photoframe_config')

            return send_file(
                tmppath,
                mimetype='application/gzip',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logging.exception('Failed to create config backup')
            return self.jsonify({'status': False, 'error': str(e)})

    def _handleImport(self):
        """Restore config from uploaded tar.gz."""
        if 'filename' not in self.getRequest().files:
            return self.jsonify({'status': False, 'error': 'No file uploaded'})

        file = self.getRequest().files['filename']
        if file.filename == '':
            return self.jsonify({'status': False, 'error': 'No file selected'})

        if not file.filename.lower().endswith('.tar.gz'):
            return self.jsonify({'status': False, 'error': 'File must be a .tar.gz archive'})

        try:
            fd, tmppath = tempfile.mkstemp(suffix='.tar.gz')
            os.close(fd)
            file.save(tmppath)

            if not self._validateTarball(tmppath):
                os.remove(tmppath)
                return self.jsonify({'status': False, 'error': 'Invalid backup: missing settings.json or path traversal detected'})

            self.slideshow.stop()

            config_folder = path.CONFIGFOLDER
            backup_folder = str(config_folder) + '.bak'
            if os.path.exists(backup_folder):
                shutil.rmtree(backup_folder)
            if config_folder.exists():
                shutil.move(str(config_folder), backup_folder)

            config_folder.mkdir(parents=True, exist_ok=True)

            with tarfile.open(tmppath, 'r:gz') as tar:
                for member in tar.getmembers():
                    member.name = member.name.replace('photoframe_config/', '', 1)
                    if member.name:
                        tar.extract(member, str(config_folder))

            os.remove(tmppath)

            self.settingsmgr.load()
            self.slideshow.start()

            return self.jsonify({'status': True, 'message': 'Config restored successfully'})

        except Exception as e:
            logging.exception('Failed to restore config backup')
            self.slideshow.start()
            return self.jsonify({'status': False, 'error': str(e)})

    def _validateTarball(self, filepath):
        """Validate tarball contains settings.json and no path traversal."""
        try:
            has_settings = False
            with tarfile.open(filepath, 'r:gz') as tar:
                for member in tar.getmembers():
                    if '..' in member.name or member.name.startswith('/'):
                        logging.warning(f'Path traversal detected in backup: {member.name}')
                        return False
                    if member.name.endswith('settings.json'):
                        has_settings = True
            return has_settings
        except Exception as e:
            logging.exception('Failed to validate tarball')
            return False
