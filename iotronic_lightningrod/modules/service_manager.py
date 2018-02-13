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

__author__ = "Nicola Peditto <npeditto@unime.it"

import inspect
import os
import signal
import subprocess
from urllib.parse import urlparse

from iotronic_lightningrod.modules import Module
from iotronic_lightningrod.modules import utils

import iotronic_lightningrod.wampmessage as WM


from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class ServiceManager(Module.Module):

    def __init__(self, board, session):
        super(ServiceManager, self).__init__("ServiceManager", board)

    def finalize(self):
        pass

    async def ServiceEnable(self, name, public_port, local_port):

        LOG.info("RPC " + utils.getFuncName()
                 + " CALLED for " + name + " service:")

        try:

            url_ip = urlparse(self.board.wamp_config["url"])[1].split(':')[0]

            # "wstun -r6030:127.0.0.1:22 ws://192.168.17.103:8080"
            opt_reverse = "-r" + str(public_port) + ":127.0.0.1:" \
                          + str(local_port)
            wagent_url = "ws://" + url_ip + ":8080"

            wstun = subprocess.Popen(
                ['/usr/bin/wstun', opt_reverse, wagent_url],
                stdout=subprocess.PIPE
            )

            LOG.debug(" - WSTUN stdout: " + str(wstun.stdout))

            message = "Cloud service " + str(name) + " exposed on port " \
                      + str(public_port) + " on " + url_ip

            LOG.info(" - " + message + " with PID " + str(wstun.pid))

            w_msg = WM.WampSuccess([wstun.pid, message])

        except Exception as err:
            message = "Error exposing " + str(name) + " service: " + str(err)
            LOG.error(" - " + message)
            w_msg = WM.WampError(message)

        return w_msg.serialize()

    async def ServiceDisable(self, name, pid):

        LOG.info("RPC " + utils.getFuncName() + " CALLED for "
                 + name + " service:")

        try:

            os.kill(pid, signal.SIGKILL)

            message = "Cloud service " + str(name) + " disabled."

            LOG.info(" - " + message)
            w_msg = WM.WampSuccess(message)

        except Exception as err:
            message = "Error disabling " + str(name) + " service: " + str(err)
            LOG.error(" - " + message)
            w_msg = WM.WampError(message)

        return w_msg.serialize()

    async def ServiceRestore(self, name, public_port, local_port, pid):

        LOG.info("RPC " + utils.getFuncName() + " CALLED for "
                 + name + " service:")

        try:

            # 1. Kill wstun process (if exists)
            try:
                os.kill(pid, signal.SIGKILL)
                LOG.info(" - service " + name + " with PID " + str(pid)
                         + " killed.")
            except OSError:
                LOG.warning(" - WSTUN process already killed: "
                            "creating new one...")

            # 2. Create the reverse tunnel
            url_ip = urlparse(self.board.wamp_config["url"])[1].split(':')[0]
            opt_reverse = "-r" + str(public_port) + ":127.0.0.1:" + str(
                local_port)
            wagent_url = "ws://" + url_ip + ":8080"
            wstun = subprocess.Popen(
                ['/usr/bin/wstun', opt_reverse, wagent_url],
                stdout=subprocess.PIPE
            )

            message = "service " + str(name) + " restored on port " \
                      + str(public_port) + " on " + url_ip
            LOG.info(" - " + message + " with PID " + str(wstun.pid))
            w_msg = WM.WampSuccess([wstun.pid, message])

        except Exception as err:
            message = "Error restoring " + str(name) + " service: " + str(err)
            LOG.error(" - " + message)
            w_msg = WM.WampError(message)

        return w_msg.serialize()
