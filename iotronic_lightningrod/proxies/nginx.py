# Copyright 2011 OpenStack Foundation
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


from iotronic_lightningrod.proxies import Proxy

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


import json
import os
import site
import subprocess
import time

from iotronic_lightningrod.common.exception import NginxError
from iotronic_lightningrod.modules import utils
import iotronic_lightningrod.wampmessage as WM
from subprocess import call


class ProxyManager(Proxy.Proxy):

    def __init__(self):
        super(ProxyManager, self).__init__("nginx")

    def finalize(self):
        """Function called at the end of module loading (after RPC registration).

        :return:

        """
        pass

    def _proxyInfo(self):

        nginxMsg = {}

        try:
            stat = subprocess.Popen('systemctl status nginx.service',
                                    shell=True, stdout=subprocess.PIPE)
            stdout_list = str(stat.communicate()[0]).split('\n')
            for line in stdout_list:
                if 'Active:' in line:

                    nginxMsg['log'] = line.split('\\n')[2].replace("   ", "")

                    if '(running)' in line:
                        nginxMsg['status'] = True
                    else:
                        nginxMsg['status'] = False

                    nginxMsg = json.dumps(nginxMsg)

                    return nginxMsg

        except Exception as err:
            LOG.error("Error check NGINX status: " + str(err))
            nginxMsg['log'] = str(err)
            nginxMsg['status'] = False
            nginxMsg = json.dumps(nginxMsg)
            return nginxMsg

    def _proxyStatus(self):

        nginxMsg = {}

        try:

            stat = subprocess.Popen(
                'systemctl status nginx.service',
                shell=True,
                stdout=subprocess.PIPE
            )
            stdout_list = str(stat.communicate()[0]).split('\n')
            for line in stdout_list:
                if 'Active:' in line:
                    if '(running)' in line:
                        nginxMsg['log'] = "NGINX is running"
                        nginxMsg['status'] = True
                        # LOG.info("--> " + nginxMsg['log'])
                    else:
                        nginxMsg['log'] = "NGINX is not running"
                        nginxMsg['status'] = False
                        # LOG.warning("--> " + nginxMsg['log'])

        except Exception as err:
            nginxMsg['log'] = "Error check NGINX status: " + str(err)
            nginxMsg['status'] = True
            # LOG.error("--> " + nginxMsg['log'])

        return json.dumps(nginxMsg)

    def _proxyReload(self):

        nginxMsg = {}

        try:

            stat = subprocess.call('service nginx reload', shell=True)

            if stat != 0:
                raise NginxError(str(stat))

            else:
                nginxMsg['log'] = "NGINX successfully reloaded"
                nginxMsg['code'] = stat
                LOG.info("--> " + nginxMsg['log'])

        except NginxError:
            nginxMsg['log'] = "NGINX reloading error"
            nginxMsg['code'] = stat
            LOG.warning("--> " + nginxMsg['log'])

        except Exception as err:
            nginxMsg['log'] = "NGINX Generic error: " + str(err)
            nginxMsg['code'] = stat
            LOG.warning("--> " + nginxMsg['log'])

        nginxMsg = json.dumps(nginxMsg)
        return nginxMsg

    def _proxyRestart(self):

        nginxMsg = {}

        try:
            stat = os.system('systemctl restart nginx')

            if stat != 0:
                raise NginxError(str(stat))

            else:
                nginxMsg['log'] = "NGINX successfully restart"
                nginxMsg['code'] = stat
                LOG.info("--> " + nginxMsg['log'])

        except NginxError:
            nginxMsg['log'] = "NGINX restarting error"
            nginxMsg['code'] = stat
            LOG.warning("--> " + nginxMsg['log'])

        except Exception as err:
            nginxMsg['log'] = "NGINX generic error: " + str(err)
            nginxMsg['code'] = stat
            LOG.warning("--> " + nginxMsg['log'])

        return json.dumps(nginxMsg)

    def _proxyBoardDnsSetup(self, board_dns, owner_email):

        nginxMsg = {}

        try:

            py_dist_pack = site.getsitepackages()[0]

            iotronic_nginx_path = "/etc/nginx/conf.d/iotronic"
            iotronic_nginx_default = "/etc/nginx/conf.d/iotronic/default"

            if not os.path.exists(iotronic_nginx_path):
                os.makedirs(iotronic_nginx_path)

            nginx_default = '''proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";'''

            with open(iotronic_nginx_default, "w") as text_file:
                text_file.write("%s" % nginx_default)

            iotronic_nginx_avl_path = "/etc/nginx/sites-available/iotronic"

            string = '''server {{
                   listen 80;

                   server_name {0};
                   include conf.d/iotronic/*;
               }}'''.format(board_dns)

            with open(iotronic_nginx_avl_path, "w") as text_file:
                text_file.write("%s" % string)

            os.system(
                'ln -s '
                '/etc/nginx/sites-available/iotronic '
                '/etc/nginx/sites-enabled/'
            )

            time.sleep(3)
            self._proxyReload()
            time.sleep(3)

            command = '/usr/bin/certbot -n ' \
                      '--redirect --authenticator webroot ' \
                      '--installer nginx -w /var/www/html/ ' \
                      '--domain ' + board_dns + ' --agree-tos ' \
                      '--email ' + owner_email

            LOG.debug(command)
            call(command, shell=True)

        except Exception as err:
            nginxMsg['log'] = "NGINX DNS setup error: " + str(err)
            nginxMsg['code'] = ""
            LOG.warning("--> " + nginxMsg['log'])

        return json.dumps(nginxMsg)

    def _exposeWebservice(self, service_name, local_port):

        nginxMsg = {}

        try:

            nginx_path = "/etc/nginx/conf.d/iotronic"

            if not os.path.exists(nginx_path):
                os.makedirs(nginx_path)

            fp = nginx_path + "/" + service_name

            string = '''location /{0}/ {{
                    proxy_pass http://localhost:{1}/;
                include conf.d/iotronic/default;
            }}

            location /{0} {{
                rewrite ^ $scheme://$http_host/{0}/ redirect;
            }}
            '''.format(service_name, local_port)

            with open(fp, "w") as ws_nginx_conf:
                ws_nginx_conf.write("%s" % string)

            time.sleep(3)

            nginxMsg['message'] = "Webservice '" + service_name + \
                                  "' configuration injected in NGINX."
            nginxMsg['result'] = "SUCCESS"
            LOG.info("--> " + nginxMsg['message'])

            self._proxyReload()

            time.sleep(3)

        except Exception as e:
            nginxMsg['message'] = "Error exposing Webservice '" + \
                                  service_name + \
                                  "' configuration in NGINX: {}".format(e)
            nginxMsg['result'] = "ERROR"
            LOG.warning("--> " + nginxMsg['message'])

        return json.dumps(nginxMsg)

    def _disableWebservice(self, service_name):

        nginxMsg = {}

        try:

            nginx_path = "/etc/nginx/conf.d/iotronic"
            service_path = nginx_path + "/" + service_name

            if os.path.exists(service_path):

                os.remove(service_path)

                time.sleep(3)

                nginxMsg['message'] = "webservice '" \
                                      + service_name + "' disabled."
                nginxMsg['result'] = "SUCCESS"
                # LOG.info("--> " + nginxMsg['message'])

                self._proxyReload()

                time.sleep(3)

            else:
                nginxMsg['message'] = "webservice file " \
                    + service_path + " does not exist"
                nginxMsg['result'] = "ERROR"
                # LOG.info("--> " + nginxMsg['message'])

        except Exception as e:
            nginxMsg['message'] = "Error disabling Webservice '" + \
                                  service_name + "': {}".format(e)
            nginxMsg['result'] = "ERROR"
            # LOG.warning("--> " + nginxMsg['message'])

        return json.dumps(nginxMsg)

    def _webserviceList(self):

        nginx_path = "/etc/nginx/conf.d/iotronic"

        if os.path.exists(nginx_path):
            service_list = [f for f in os.listdir(nginx_path)
                            if os.path.isfile(os.path.join(nginx_path, f))]

            service_list.remove('default')
        else:
            service_list = []

        return service_list

    async def NginxInfo(self):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        message = self._proxyInfo()
        w_msg = WM.WampSuccess(message)

        return w_msg.serialize()

    async def NginxStatus(self):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        message = self._proxyStatus()
        w_msg = WM.WampSuccess(message)

        return w_msg.serialize()

    async def NginxReload(self):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        message = self._proxyReload()
        w_msg = WM.WampSuccess(message)

        return w_msg.serialize()

    async def NginxRestart(self):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        message = self._proxyRestart()
        w_msg = WM.WampSuccess(message)

        return w_msg.serialize()

    async def NginxIotronicConf(self):

        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        message = self._proxyIotronicConf()
        w_msg = WM.WampSuccess(message)

        return w_msg.serialize()
