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

# Linino references: http://wiki.linino.org/doku.php?id=wiki:lininoio_sysfs

from twisted.internet.defer import returnValue

from iotronic_lightningrod.devices import Device
from iotronic_lightningrod.devices.gpio import yun

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class System(Device.Device):

    def __init__(self):
        super(System, self).__init__("yun")

        self.gpio = yun.YunGpio()

        self.gpio.EnableGPIO()

    def finalize(self):
        """Function called at the end of module loading (after RPC registration).

        :return:

        """
        pass

    def testLED(self):
        LOG.info(" - testLED CALLED...")

        yield self.gpio.blinkLed()

        result = "testLED: LED blinking!\n"
        LOG.info(result)
        returnValue(result)

    def setGPIOs(self, Dpin, direction, value):

        LOG.info(" - setGPIOs CALLED... digital pin " + Dpin
                 + " (GPIO n. " + self.gpio.MAPPING[Dpin] + ")")

        result = yield self.gpio._setGPIOs(Dpin, direction, value)
        LOG.info(result)
        returnValue(result)

    def readVoltage(self, Apin):
        """To read the voltage applied on the pin A0,A1,A2,A3,A4,A5

        """
        LOG.info(" - readVoltage CALLED... reading pin " + Apin)

        voltage = self.gpio._readVoltage(Apin)

        result = yield "read voltage for " + Apin + " pin: " + voltage
        LOG.info(result)
        returnValue(result)
