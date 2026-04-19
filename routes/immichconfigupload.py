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
import json

from .baseroute import BaseRoute

class RouteImmichConfigUpload(BaseRoute):
    def setupex(self, servicemgr, slideshow):
        self.servicemgr = servicemgr
        self.slideshow = slideshow

        self.addUrl('/service/<service>/immichconfig').clearMethods().addMethod('POST').addMethod('GET')

    def handle(self, app, **kwargs):
        service = kwargs.get('service')
        if not service:
            logging.error('No service specified for Immich config upload')
            return self.setAbort(400)

        if self.getRequest().method == 'POST':
            # Handle Immich config - either JSON body or file upload
            content_type = self.getRequest().content_type or ''
            data = None

            if 'application/json' in content_type:
                # Direct JSON POST from inline form
                try:
                    data = self.getRequest().get_json()
                    if not data:
                        logging.error('Empty JSON body in Immich config POST')
                        return 'Empty JSON body', 400
                except Exception as e:
                    logging.error(f'Failed to parse JSON body: {e}')
                    return 'Invalid JSON in request body', 400
            elif 'filename' in self.getRequest().files:
                # File upload path (existing behavior)
                file = self.getRequest().files['filename']
                if file.filename == '':
                    logging.error('No file selected for Immich config upload')
                    return 'No file selected', 400
                try:
                    data = json.load(file)
                except json.JSONDecodeError as e:
                    logging.error(f'Invalid JSON in Immich config file: {e}')
                    return 'Invalid JSON format in Immich configuration file', 400
            else:
                logging.error('No JSON body or file in Immich config upload')
                return 'Provide JSON body or file upload', 400

            try:
                logging.info(f'Immich config upload for service {service}: {len(str(data))} bytes')

                # Validate first to get detailed error messages
                validation_result = self.servicemgr.validateImmichServiceConfiguration(service, data)
                if validation_result is not True and validation_result is not None:
                    logging.error(f'Immich config validation failed: {validation_result}')
                    return f'Immich configuration is invalid: {validation_result}', 400

                # Set configuration (also validates internally, but we already checked)
                if self.servicemgr.setImmichServiceConfiguration(service, data):
                    self.slideshow.trigger()
                    return 'Immich configuration uploaded successfully', 200
                else:
                    return 'Service does not support Immich configuration', 400

            except Exception as e:
                logging.error(f'Error processing Immich config upload: {e}')
                return 'Error processing Immich configuration file', 500
                
        elif self.getRequest().method == 'GET':
            # Handle Immich config retrieval
            try:
                config = self.servicemgr.getImmichServiceConfiguration(service)
                if config is None:
                    logging.warning(f'No Immich configuration found for service: {service}')
                    return 'No Immich configuration found for this service', 404
                
                logging.info(f'Retrieved Immich config for service {service}')
                return self.jsonify(config)
                
            except Exception as e:
                logging.error(f'Error retrieving Immich config for service {service}: {e}')
                return 'Error retrieving Immich configuration', 500
        else:
            return self.setAbort(405)