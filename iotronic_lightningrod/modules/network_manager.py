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

import asyncio
from iotronic_lightningrod.modules import Module
import iotronic_lightningrod.wampmessage as WM
from oslo_log import log as logging
import subprocess
import time
from urllib.parse import urlparse

LOG = logging.getLogger(__name__)

Port = []

interface = ""


class NetworkManager(Module.Module):

    def __init__(self, board, session):

        super(NetworkManager, self).__init__("NetworkManager", board)
        self.url_ip = urlparse(board.wamp_config["url"])[1].split(':')[0]
        self.wagent_url = "ws://" + self.url_ip + ":8080"

    def finalize(self):
        pass

    def restore(self):
        pass

    async def Create_VIF(self, r_tcp_port):

        LOG.info("Creation of the VIF ")

        inter_num = 30000 - int(r_tcp_port)
        global Port
        Port.insert(0, inter_num)

        LOG.debug("Creation of the VIF iotronic" + str(r_tcp_port))

        try:

            p1 = subprocess.Popen('socat -d -d TCP-L:' + str(inter_num) +
                                  ',bind=localhost,reuseaddr,forever,'
                                  'interval=10 TUN,tun-type=tap,'
                                  'tun-name=iotronic'
                                  + str(inter_num) + ',up  ',
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)

            p1 = subprocess.Popen('wstun -r' + str(r_tcp_port) + ':localhost:'
                                  + str(inter_num) + ' '
                                  + str(self.wagent_url),
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)

            LOG.debug('Creation of the VIF succeded: iotronic')

            global interface
            interface = 'iotronic' + str(inter_num)
            message = 'WS tun and SOCAT created'
            w_msg = WM.WampSuccess(message)

        except Exception:

            LOG.error('Error while creating the virtual interface')
            message = 'Error while the creation'
            w_msg = WM.WampError(message)

        return w_msg.serialize()

    async def Configure_VIF(self, port, cidr):

        LOG.info("Configuration of the VIF")

        try:
            LOG.debug("Configuration of the VIF " + interface)

            p3 = subprocess.Popen("ip link set dev " + interface + " address "
                                  + str(port['MAC_add']),
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)

            time.sleep(1)

            p5 = subprocess.Popen("ip address add " + str(port['ip']) + "/"
                                  + str(cidr) + " dev " + interface,
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)

            message = 'IP address assigned'
            w_msg = WM.WampSuccess(message)

            LOG.info("Configuration succeded")

        except Exception as e:

            LOG.error(str(e))
            message = 'Error while the configuration'
            w_msg = WM.WampError(message)

        return w_msg.serialize()

    async def Remove_VIF(self, VIF_name):

        LOG.info("Removing a VIF from the board")

        try:
            LOG.info("Removing VIF")
            inter_num = 30000 - int(VIF_name[8:])
            LOG.debug("Removing VIF : iotronic" + str(inter_num))

            p1 = subprocess.\
                Popen("kill $(ps aux | grep -e '-r'"
                      + str(VIF_name[8:]) + " | awk '{print $2}')",
                      shell=True,
                      stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT)

            global Port
            Port.remove(inter_num)

            message = 'VIF removed'
            w_msg = WM.WampSuccess(message)

            LOG.info("VIF removed")
        except Exception as e:

            LOG.error(str(e))
            message = 'Error while removing the VIF'
            w_msg = WM.WampError(message)

        return w_msg.serialize()
