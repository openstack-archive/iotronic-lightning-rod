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

import importlib as imp
import inspect
import os
import subprocess

from datetime import datetime

from iotronic_lightningrod.config import package_path
from iotronic_lightningrod.lightningrod import RPC_devices
from iotronic_lightningrod.lightningrod import SESSION
from iotronic_lightningrod.modules import Module
from iotronic_lightningrod.modules import utils


from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class DeviceManager(Module.Module):

    def __init__(self, board, session):

        # Module declaration
        super(DeviceManager, self).__init__("DeviceManager", board)

        self.device_session = session

        device_type = board.type

        path = package_path + "/devices/" + device_type + ".py"

        if os.path.exists(path):

            device_module = imp.import_module(
                "iotronic_lightningrod.devices." + device_type
            )

            LOG.info(" - Device '" + device_type + "' module imported!")

            device = device_module.System()

            dev_meth_list = inspect.getmembers(
                device,
                predicate=inspect.ismethod
            )

            RPC_devices[device_type] = dev_meth_list

            self._deviceWampRegister(dev_meth_list, board)

            board.device = device

        else:
            LOG.warning("Device '" + device_type + "' not supported!")

    def finalize(self):
        pass

    def restore(self):
        pass

    def _deviceWampRegister(self, dev_meth_list, board):

        LOG.info(" - " + str(board.type).capitalize()
                 + " device registering RPCs:")

        for meth in dev_meth_list:

            if (meth[0] != "__init__") & (meth[0] != "finalize"):
                # LOG.info(" - " + str(meth[0]))
                rpc_addr = u'iotronic.' + board.uuid + '.' + meth[0]
                # LOG.debug(" --> " + str(rpc_addr))
                SESSION.register(meth[1], rpc_addr)

                LOG.info("   --> " + str(meth[0]) + " registered!")

    async def DevicePing(self):
        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

    async def DeviceReboot(self):
        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        command = "reboot"
        subprocess.call(command, shell=True)

        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

    async def DeviceHostname(self):
        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        command = "hostname"
        # subprocess.call(command, shell=True)

        out = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE
        )

        output = out.communicate()[0].decode('utf-8').strip()
        print(output)

        return str(output) + "@" + \
            str(datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))

    """
    async def DeviceWampDisconnect(self):
        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        import threading, time

        def delayDisconnection():
            time.sleep(5)
            SESSION.disconnect()

        threading.Thread(target=delayDisconnection).start()

        return "Device disconnection in 5 seconds..."
    """
