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

import os
import time

from iotronic_lightningrod.devices.gpio import Gpio

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

i2c_path = "/sys/devices/mcuio/0:0.0/0:1.4/i2c-0"
device1_path = i2c_path + "/0-0060/iio:device1/"
device0_path = "/sys/bus/iio/devices/iio:device0/"


class YunGpio(Gpio.Gpio):

    def __init__(self):
        super(YunGpio, self).__init__("yun")

        self.MAPPING = {
            'D8': '104',
            'D9': '105',
            'D10': '106',
            'D11': '107',
            'D5': '114',
            'D13': '115',
            'D3': '116',
            'D2': '117',
            'D4': '120',
            'D12': '122',
            'D6': '123'}

        # LOG.info("Arduino YUN gpio module importing...")

    def EnableGPIO(self):
        """Enable GPIO (device0).

        """
        try:

            with open('/sys/bus/iio/devices/iio:device0/enable', 'a') as f:
                f.write('1')

            result = "  - GPIO enabled!\n"
            LOG.info(result)

        except Exception as err:
            LOG.error("Error enabling GPIO (device0): " + str(err))

    def DisableGPIO(self):
        """Disable GPIO (device0).

        """
        try:
            with open('/sys/bus/iio/devices/iio:device0/enable', 'a') as f:
                f.write('0')

            result = "  - GPIO disabled!\n"
            LOG.info(result)
        except Exception as err:
            LOG.error("Error disabling GPIO (device0): " + str(err))

    def EnableI2c(self):
        """Enable i2c device (device1).

        From ideino-linino-lib library:
            Board.prototype.addI2c = function(name, driver, addr, bus)
                board.addI2c('BAR', 'mpl3115', '0x60', 0):
                - i2c_device.driver: mpl3115
                - i2c_device.addr: 0x60
                - i2c_device.name: BAR
                - i2c_device.bus: 0

        """

        try:

            if os.path.exists('/sys/bus/i2c/devices/i2c-0/0-0060'):
                result = "  - I2C device already enabled!"

            else:

                with open('/sys/bus/i2c/devices/i2c-0/new_device', 'a') as f:
                    # 'echo '+i2c_device.driver+' '+i2c_device.addr+ '
                    f.write('mpl3115 0x60')
                    result = "  - I2C device enabled!"

            LOG.info(result)

        except Exception as err:
            LOG.error("Error enabling I2C (device1): " + str(err))

    def i2cRead(self, sensor):
        """Read i2c raw value.

        sensor options:
        - in_pressure_raw
        - in_temp_raw

        :param sensor: name of the sensor connected to I2C port
        :return: I2C raw value

        """
        try:

            with open(device1_path + "in_" + sensor + "_raw") as raw:
                value = raw.read()

        except Exception as err:
            LOG.error("Error reading I2C device: " + str(err))
            value = None

        return value

    def setPIN(self, DPIN, value):
        """Function to set digital PIN value.

        :param DPIN: pin
        :param value: value to set the pin

        """
        try:
            with open('/sys/class/gpio/' + DPIN + '/value', 'a') as f:
                f.write(value)

        except Exception as err:
            LOG.error("Error setting PIN value: " + str(err))

    def _setGPIOs(self, Dpin, direction, value):
        """GPIO mapping on lininoIO

            -------------------------
            GPIO n.     OUTPUT
            104	        D8
            105	        D9
            106	        D10
            107	        D11
            114	        D5
            115	        D13
            116	        D3
            117	        D2
            120	        D4
            122	        D12
            123	        D6

        """

        try:

            with open('/sys/class/gpio/export', 'a') as f_export:
                f_export.write(self.MAPPING[Dpin])

            with open('/sys/class/gpio/' + Dpin + '/direction', 'a') as f_dir:
                f_dir.write(direction)

            with open('/sys/class/gpio/' + Dpin + '/value', 'a') as f_value:
                f_value.write(value)

            with open('/sys/class/gpio/' + Dpin + '/value') as f_value:
                result = "PIN " + Dpin + " value " + f_value.read()

        except Exception as err:
            LOG.error("Error setting GPIO value: " + str(err))
            result = None

        return result

    def _readVoltage(self, pin):

        try:
            with open(device0_path + "in_voltage_" + pin + "_raw") as raw:
                voltage = raw.read()
                # print("VOLTAGE: " + voltage)

        except Exception as err:
            LOG.error("Error reading voltage: " + str(err))
            voltage = None

        return voltage

    def blinkLed(self):
        """LED: 13. There is a built-in LED connected to digital pin 13.

        When the pin has HIGH value, the LED is on,
        when the pin has LOW value, it is off.

        """
        with open('/sys/class/gpio/export', 'a') as f:
            f.write('115')

        with open('/sys/class/gpio/D13/direction', 'a') as f:
            f.write('out')

        with open('/sys/class/gpio/D13/value', 'a') as f:
            f.write('1')

        time.sleep(2)

        with open('/sys/class/gpio/D13/value', 'a') as f:
            f.write('0')
