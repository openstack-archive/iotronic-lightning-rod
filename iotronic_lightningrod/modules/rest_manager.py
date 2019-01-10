# Copyright 2017 MDSLAB - University of Messina
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

__author__ = "Nicola Peditto <n.peditto@gmail.com>"

from iotronic_lightningrod.lightningrod import board
from iotronic_lightningrod.lightningrod import iotronic_status
from iotronic_lightningrod.modules import device_manager
from iotronic_lightningrod.modules import Module
from iotronic_lightningrod.modules import service_manager


from datetime import datetime
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request


import os
import subprocess
import threading


from oslo_config import cfg
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class RestManager(Module.Module):

    def __init__(self, board, session=None):
        super(RestManager, self).__init__("RestManager", board)

    def finalize(self):
        threading.Thread(target=self._runRestServer, args=()).start()

    def restore(self):
        pass

    def _runRestServer(self):

        APP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        TEMPLATE_PATH = os.path.join(APP_PATH, 'modules/web/templates/')
        STATIC_PATH = os.path.join(APP_PATH, 'modules/web/static/')

        app = Flask(
            __name__,
            template_folder=TEMPLATE_PATH,
            static_folder=STATIC_PATH,
            static_url_path="/static"
        )

        @app.route('/')
        def home():
            return render_template('home.html')

        @app.route('/status')
        def status():

            wstun_status = service_manager.wstun_status()
            if wstun_status == 0:
                wstun_status = "Online"
            else:
                wstun_status = "Offline"

            service_list = service_manager.services_list()
            if service_list == "":
                service_list = "no services exposed!"

            info = {
                'board_id': board.uuid,
                'board_name': board.name,
                'wagent': board.agent,
                'session_id': board.session_id,
                'timestamp': str(
                    datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')),
                'wstun_status': wstun_status,
                'board_reg_status': str(board.status),
                'iotronic_status': str(iotronic_status(board.status)),
                'service_list': str(service_list)
            }

            return render_template('status.html', **info)

        @app.route('/network')
        def network():
            info = {
                'ifconfig': device_manager.getIfconfig().replace('\n', '<br>')
            }
            return render_template('network.html', **info)

        def lr_config(ragent, code):
            bashCommand = "lr_configure %s %s " % (code, ragent)
            process = subprocess.Popen(bashCommand.split(),
                                       stdout=subprocess.PIPE)
            output, error = process.communicate()
            # print(output)
            return

        @app.route('/config', methods=['GET', 'POST'])
        def config():

            if request.method == 'POST':

                ragent = request.form['urlwagent']
                code = request.form['code']
                lr_config(ragent, code)
                return redirect("/status", code=302)

            else:
                if board.status == "first_boot":
                    urlwagent = request.args.get('urlwagent') or ""
                    code = request.args.get('code') or ""
                    info = {
                        'urlwagent': urlwagent,
                        'code': code
                    }
                    return render_template('config.html', **info)
                else:
                    return redirect("/status", code=302)

        app.run(host='0.0.0.0', port=1474, debug=False, use_reloader=False)
