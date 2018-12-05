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


from iotronic_lightningrod.modules.proxies import Proxy

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


import json
import os
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

            get_service = 'pidof systemd > /dev/null ' \
                          '&& echo "systemd" || echo "init.d"'
            service_cmd = subprocess.Popen(get_service,
                                           shell=True, stdout=subprocess.PIPE)

            service_mng = \
                service_cmd.communicate()[0].decode("utf-8").split("\n")[0]

            if service_mng == 'init.d':
                # print('INIT')
                stat = subprocess.Popen('service nginx status',
                                        shell=True, stdout=subprocess.PIPE)
                stdout_list = stat.communicate()[0].decode("utf-8").split("\n")

                for line in stdout_list:

                    if 'running' in line:

                        nginxMsg['log'] = stdout_list[0]

                        if 'running' in line:
                            nginxMsg['status'] = True
                        else:
                            nginxMsg['status'] = False

                        nginxMsg = json.dumps(nginxMsg)

                        return nginxMsg

            elif service_mng == 'systemd':
                # print('SYSTEMD')
                stat = subprocess.Popen('systemctl status nginx.service',
                                        shell=True, stdout=subprocess.PIPE)
                stdout_list = str(stat.communicate()[0]).split('\n')
                for line in stdout_list:
                    if 'Active:' in line:

                        nginxMsg['log'] = \
                            line.split('\\n')[2].replace("   ", "")
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

        stat = None

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

    def _nginx_conf_verify(self, fp):
        with open(fp, "r") as text_file:
            LOG.debug(text_file.read())

    def _proxyEnableWebService(self, board_dns, owner_email):

        nginxMsg = {}

        try:

            nginx_path = "/etc/nginx/conf.d/"

            nginx_board_conf_file = nginx_path + "/" + board_dns + ".conf"
            nginx_board_conf = '''server {{
                listen              80;
                server_name    {0};
            }}
            '''.format(board_dns)

            with open(nginx_board_conf_file, "w") as text_file:
                text_file.write("%s" % nginx_board_conf)

            self._nginx_conf_verify(nginx_board_conf_file)
            time.sleep(3)
            self._proxyReload()
            time.sleep(3)

            command = "/usr/bin/certbot -n " \
                      "--redirect " \
                      "--authenticator webroot " \
                      "--installer nginx " \
                      "-w /var/www/html/ " \
                      "--domain " + board_dns + " " \
                      "--agree-tos " \
                      "--email " + owner_email

            LOG.debug(command)
            certbot_result = call(command, shell=True)
            LOG.info("CERTBOT RESULT: " + str(certbot_result))

            nginxMsg['result'] = "SUCCESS"
            nginxMsg['message'] = "Webservice module enabled."
            LOG.info("--> " + nginxMsg['message'])

        except Exception as err:
            nginxMsg['log'] = "NGINX DNS setup error: " + str(err)
            nginxMsg['code'] = ""
            LOG.warning("--> " + nginxMsg['log'])

        return json.dumps(nginxMsg)

    def _exposeWebservice(self, board_dns, service_dns, local_port, dns_list):

        nginxMsg = {}

        try:

            nginx_path = "/etc/nginx/conf.d"

            service_path = nginx_path + "/" + service_dns + ".conf"
            string = '''server {{
            listen              80;
            server_name         {0};

                proxy_set_header Host $http_host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";

            location / {{
            proxy_pass http://localhost:{1};
            }}
            }}
            '''.format(service_dns, local_port)

            with open(service_path, "w") as ws_nginx_conf:
                ws_nginx_conf.write("%s" % string)

            time.sleep(3)

            self._nginx_conf_verify(service_path)

            self._proxyReload()

            time.sleep(3)

            command = "/usr/bin/certbot " \
                      "--expand -n " \
                      "--redirect " \
                      "--authenticator webroot " \
                      "--installer nginx -w /var/www/html/ " \
                      "--domain " + str(dns_list)

            command = "/usr/bin/certbot " \
                      "-n " \
                      "--redirect " \
                      "--authenticator webroot " \
                      "--installer nginx -w /var/www/html/ " \
                      "--cert-name " + str(board_dns) + " " \
                      "--domain " + str(dns_list)

            LOG.debug(command)
            certbot_result = call(command, shell=True)
            LOG.info("CERTBOT RESULT: " + str(certbot_result))

            LOG.info("Webservices list updated:\n" +
                     str(self._webserviceList()))

            nginxMsg['result'] = "SUCCESS"
            nginxMsg['message'] = "Webservice '" + service_dns + \
                                  "' exposed in NGINX."
            LOG.info(nginxMsg['message'])

        except Exception as e:
            nginxMsg['message'] = "Error exposing Webservice '" + \
                                  service_dns + \
                                  "' configuration in NGINX: {}".format(e)
            nginxMsg['result'] = "ERROR"
            LOG.warning("--> " + nginxMsg['message'])

        return json.dumps(nginxMsg)

    def _disableWebservice(self, service_dns, dns_list):
        """
        :param service:
        :param dns_list:
        :return:
        """

        nginxMsg = {}

        try:

            nginx_path = "/etc/nginx/conf.d"
            service_path = nginx_path + "/" + service_dns + ".conf"

            if os.path.exists(service_path):

                os.remove(service_path)

                time.sleep(1)

                self._proxyReload()

                time.sleep(3)

                command = "/usr/bin/certbot " \
                          "--expand -n " \
                          "--redirect " \
                          "--authenticator webroot " \
                          "--installer nginx -w /var/www/html/ " \
                          "--domain " + str(dns_list)

                LOG.debug(command)
                certbot_result = call(command, shell=True)
                LOG.info("CERTBOT RESULT: " + str(certbot_result))

                LOG.info("Webservices list updated:\n" + str(
                    self._webserviceList()))

                nginxMsg['message'] = "webservice '" \
                                      + service_dns + "' disabled."
                nginxMsg['result'] = "SUCCESS"
                LOG.info(nginxMsg['message'])

            else:
                nginxMsg['message'] = "webservice file " \
                    + service_path + " does not exist"
                nginxMsg['result'] = "ERROR"

        except Exception as e:
            nginxMsg['message'] = "Error disabling Webservice '" + \
                                  service_dns + "': {}".format(e)
            nginxMsg['result'] = "ERROR"

        return json.dumps(nginxMsg)

    def _webserviceList(self):

        nginx_path = "/etc/nginx/conf.d/"

        if os.path.exists(nginx_path):
            service_list = [f for f in os.listdir(nginx_path)
                            if os.path.isfile(os.path.join(nginx_path, f))]
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
