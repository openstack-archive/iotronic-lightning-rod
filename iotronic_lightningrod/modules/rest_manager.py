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


from iotronic_lightningrod.common.pam import pamAuthentication
from iotronic_lightningrod.common import utils
from iotronic_lightningrod.common.utils import get_version
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
from flask import send_file
from flask import session as f_session
from flask import url_for

import getpass
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

        app.secret_key = os.urandom(24).hex()  # to use flask session

        UPLOAD_FOLDER = '/tmp'
        ALLOWED_EXTENSIONS = set(['tar.gz', 'gz'])
        ALLOWED_STTINGS_EXTENSIONS = set(['json'])
        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

        @app.route('/')
        def home():

            if 'username' in f_session:
                return render_template('home.html')
            else:
                return render_template('login.html')

        def redirect_dest(fallback):
            dest = request.args.get('next')

            try:
                dest_url = url_for(dest)
            except Exception:
                return redirect(fallback)

            return redirect(dest_url)

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            error = None

            if request.method == 'POST':

                if pamAuthentication(
                        str(request.form['username']),
                        str(request.form['password'])
                ):
                    f_session['username'] = request.form['username']
                    return redirect_dest(fallback="/")
                else:
                    error = 'Invalid Credentials. Please try again.'

            if 'username' in f_session:
                return render_template('home.html')
            else:
                return render_template('login.html', error=error)

        @app.route('/logout')
        def logout():
            # remove the username from the session if it's there
            f_session.pop('username', None)

            return redirect("/login", code=302)

        @app.route('/status')
        def status():

            if ('username' in f_session):

                f_session['status'] = str(board.status)

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
                    'service_list': str(service_list),
                    'lr_version': str(get_version("iotronic-lightningrod"))
                }

                return render_template('status.html', **info)

            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/system')
        def system():
            if 'username' in f_session:
                info = {
                    'board_status': board.status
                }
                return render_template('system.html', **info)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/network')
        def network():
            if 'username' in f_session:
                info = {
                    'ifconfig': device_manager.getIfconfig().replace(
                        '\n', '<br>'
                    )
                }
                return render_template('network.html', **info)
            else:
                return redirect(url_for('login', next=request.endpoint))

        def lr_config(ragent, code):
            bashCommand = "lr_configure %s %s " % (code, ragent)
            process = subprocess.Popen(bashCommand.split(),
                                       stdout=subprocess.PIPE)
            output, error = process.communicate()

            return

        def lr_install():
            bashCommand = "lr_install"
            process = subprocess.Popen(bashCommand.split(),
                                       stdout=subprocess.PIPE)
            output, error = process.communicate()

            return

        def identity_backup():
            bashCommand = "device_bkp_rest backup --path /tmp "\
                          + "| grep filename: |awk '{print $4}'"
            process = subprocess.Popen(bashCommand,
                                       stdout=subprocess.PIPE, shell=True)
            output, error = process.communicate()

            return output.decode('ascii').strip()

        def identity_restore(filepath):
            bashCommand = "device_bkp_rest restore " + filepath + "| tail -n 1"
            process = subprocess.Popen(bashCommand,
                                       stdout=subprocess.PIPE, shell=True)
            output, error = process.communicate()

            return output.decode('ascii').strip()

        def allowed_file(filename):
            return '.' in filename and \
                   filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

        def allowed_settings(filename):
            return '.' in filename and \
                   filename.rsplit('.', 1)[1].lower() \
                   in ALLOWED_STTINGS_EXTENSIONS

        @app.route('/restore', methods=['GET', 'POST'])
        def upload_file():

            if 'username' in f_session:
                f_session['status'] = str(board.status)

                if request.form.get('dev_rst_btn') == 'Device restore':

                    if 'rst_file' not in request.files:

                        error = 'Identity restore result: No file uploaded!'
                        print(" - " + error)
                        info = {
                            'board_status': board.status
                        }
                        return render_template(
                            'config.html',
                            **info,
                            error=error
                        )

                    else:

                        file = request.files['rst_file']

                        if file.filename == '':

                            error = 'Identity restore result: No filename!'
                            print(" - " + error)
                            info = {
                                'board_status': board.status
                            }
                            return render_template('config.html', **info,
                                                   error=error)

                        else:
                            filename = file.filename
                            print("Identity file uploaded: " + str(filename))

                            if file and allowed_file(file.filename):
                                bpath = os.path.join(
                                    app.config['UPLOAD_FOLDER'],
                                    filename
                                )
                                file.save(bpath)
                                out_res = identity_restore(bpath)
                                print("--> restore result: " + str(out_res))
                                # restart LR
                                print("--> LR restarting in 5 seconds...")
                                f_session['status'] = "restarting"
                                utils.LR_restart_delayed(5)

                                return redirect("/", code=302)

                            else:
                                error = 'Identity restore result: ' \
                                        + 'file extention not allowed!'
                                print(" - " + error)
                                info = {
                                    'board_status': board.status
                                }
                                return render_template(
                                    'config.html',
                                    **info,
                                    error=error
                                )
                                return redirect("/config", code=302)

                else:
                    return redirect("/", code=302)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/backup', methods=['GET'])
        def backup_download():

            if 'username' in f_session:

                print("Identity file downloading: ")

                filename = identity_backup()
                print("--> backup created:" + str(filename))

                path = str(filename)
                if path is None:
                    print("Error path None")
                try:
                    print("--> backup file sent.")
                    return send_file(path, as_attachment=True)
                except Exception as e:
                    print(e)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/factory', methods=['GET'])
        def factory_reset():
            if 'username' in f_session:

                print("Lightning-rod factory reset: ")

                f_session['status'] = str(board.status)

                # delete nginx conf.d files
                os.system("rm /etc/nginx/conf.d/lr_*")
                print("--> NGINX settings deleted.")

                # delete letsencrypt
                os.system("rm -r /etc/letsencrypt")
                print("--> LetsEncrypt settings deleted.")

                # delete var-iotronic
                os.system("rm -r /var/lib/iotronic")
                print("--> Iotronic data deleted.")

                # delete etc-iotronic
                os.system("rm -r /etc/iotronic")
                print("--> Iotronic settings deleted.")

                # exec lr_install
                lr_install()

                # restart LR
                print("--> LR restarting in 5 seconds...")
                f_session['status'] = "restarting"
                utils.LR_restart_delayed(5)

                return redirect("/", code=302)
            else:
                return redirect(url_for('login', next=request.endpoint))

        @app.route('/config', methods=['GET', 'POST'])
        def config():

            if ('username' in f_session) or str(board.status) == "first_boot":

                f_session['status'] = str(board.status)

                if request.method == 'POST':

                    if request.form.get('reg_btn') == 'CONFIGURE':
                        ragent = request.form['urlwagent']
                        code = request.form['code']
                        lr_config(ragent, code)
                        return redirect("/status", code=302)

                    elif request.form.get('rst_btn') == 'RESTORE':
                        utils.restoreConf()
                        print("Restored")
                        f_session['status'] = "restarting"
                        return redirect("/", code=302)

                    elif request.form.get('fct_btn'):
                        utils.restoreFactoryConf()
                        print("Refactored")
                        print("--> LR restarting in 5 seconds...")
                        f_session['status'] = "restarting"
                        utils.LR_restart_delayed(5)
                        return redirect("/", code=302)

                    elif request.form.get('rst_settings_btn'):

                        print("Settings restoring from uploaded backup...")

                        if len(request.files) != 0:

                            if 'rst_settings_file' in request.files:

                                file = request.files['rst_settings_file']

                                if file.filename == '':

                                    error = 'Settings restore result: ' \
                                            + 'No filename!'
                                    print(" - " + error)
                                    info = {
                                        'board_status': board.status
                                    }
                                    return render_template(
                                        'config.html',
                                        **info,
                                        error=error
                                    )

                                else:

                                    filename = file.filename
                                    print(" - file uploaded: " + str(filename))

                                    if file and allowed_settings(filename):
                                        bpath = os.path.join(
                                            app.config['UPLOAD_FOLDER'],
                                            filename
                                        )
                                        file.save(bpath)

                                        try:
                                            os.system(
                                                'cp '
                                                + bpath
                                                + ' /etc/iotronic/'
                                                + 'settings.json'
                                            )
                                        except Exception as e:
                                            LOG.warning(
                                                "Error restoring " +
                                                "configuration " + str(e))

                                        print(" - done!")

                                        if board.status == "first_boot":
                                            # start LR
                                            print(" - LR starting "
                                                  + "in 5 seconds...")
                                            f_session['status'] = "starting"

                                        else:
                                            # restart LR
                                            print(" - LR restarting "
                                                  + "in 5 seconds...")
                                            f_session['status'] = "restarting"
                                            utils.LR_restart_delayed(5)

                                        return redirect("/", code=302)

                                    else:
                                        error = 'Wrong file extention: ' \
                                                + str(filename)
                                        print(" - " + error)
                                        info = {
                                            'board_status': board.status
                                        }
                                        return render_template(
                                            'config.html',
                                            **info,
                                            error=error
                                        )

                            else:
                                error = 'input form error!'
                                print(" - " + error)
                                info = {
                                    'board_status': board.status
                                }
                                return render_template('config.html', **info,
                                                       error=error)

                        else:
                            error = "no settings file specified!"
                            print(" - " + error)
                            info = {
                                'board_status': board.status
                            }
                            return render_template(
                                'config.html',
                                **info,
                                error=error
                            )

                        return redirect("/config", code=302)

                    else:
                        print("Error POST request")
                        return redirect("/status", code=302)

                else:

                    if board.status == "first_boot":

                        urlwagent = request.args.get('urlwagent') or ""
                        code = request.args.get('code') or ""
                        info = {
                            'urlwagent': urlwagent,
                            'code': code,
                            'board_status': board.status
                        }

                        return render_template('config.html', **info)

                    else:

                        if request.args.get('bkp_btn'):
                            # utils.backupConf()
                            print("Settings file downloading: ")
                            path = "/etc/iotronic/settings.json"
                            if path is None:
                                print("Error path None")
                                return redirect("/config", code=500)

                            try:
                                fn_download = "settings_" + str(
                                    datetime.now().strftime(
                                        '%Y-%m-%dT%H:%M:%S.%f')) + ".json"
                                print("--> backup settings file sent.")
                                return send_file(
                                    path,
                                    as_attachment=True,
                                    attachment_filename=fn_download
                                )

                            except Exception as e:
                                print(e)
                                return redirect("/config", code=500)

                        elif request.args.get('rst_btn'):
                            utils.restoreConf()
                            print("Restored")
                            return redirect("/config", code=302)

                        elif request.args.get('fct_btn'):
                            utils.restoreFactoryConf()
                            print("Refactored")
                            print("--> LR restarting in 5 seconds...")
                            f_session['status'] = "restarting"
                            utils.LR_restart_delayed(5)
                            return redirect("/", code=302)

                        elif request.args.get('lr_restart_btn'):
                            print("LR restarting in 5 seconds...")
                            f_session['status'] = "restarting"
                            utils.LR_restart_delayed(5)
                            return redirect("/", code=302)

                        else:

                            info = {
                                'board_status': board.status
                            }
                            return render_template('config.html', **info)

            else:
                return redirect(url_for('login', next=request.endpoint))

        app.run(host='0.0.0.0', port=1474, debug=False, use_reloader=False)
