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

import inspect

from iotronic_lightningrod.devices import Device
from iotronic_lightningrod.devices.gpio import raspberry

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


def whoami():
    return inspect.stack()[1][3]


def makeNothing():
    pass


class System(Device.Device):

    def __init__(self):
        super(System, self).__init__("raspberry")

        raspberry.RaspberryGpio().EnableGPIO()

    def finalize(self):
        """Function called at the end of module loading (after RPC registration).

        :return:

        """
        pass

    async def testRPC(self):
        rpc_name = whoami()
        LOG.info("RPC " + rpc_name + " CALLED...")
        await makeNothing()
        result = " - " + rpc_name + " result: testRPC is working!!!\n"
        LOG.info(result)
        return result
