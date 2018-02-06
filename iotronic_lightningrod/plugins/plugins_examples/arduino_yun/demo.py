# Copyright 2017 MDSLAB - University of Messina
#    All Rights Reserved.
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

from iotronic_lightningrod.devices.gpio import yun
from iotronic_lightningrod.plugins import Plugin

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

# User imports
import datetime
import math
import time

ADCres = 1023.0
Beta = 3950
Kelvin = 273.15
Rb = 10000
Ginf = 120.6685

# User global variables
resource_id = ""  # temperature resource id
action_URL = "http://smartme-data.unime.it/api/3/action/datastore_upsert"
api_key = ''
headers = {
    "Content-Type": "application/json",
    'Authorization': "" + api_key + ""
}
polling_time = 10


class Worker(Plugin.Plugin):
    def __init__(self, name, params=None):
        super(Worker, self).__init__(name, params)

    def run(self):

        device = yun.YunGpio()

        while (self._is_running):

            voltage = device._readVoltage("A0")

            Rthermistor = float(Rb) * (float(ADCres) / float(voltage) - 1)

            rel_temp = float(Beta) / (math.log(
                float(Rthermistor) * float(Ginf))
            )
            temp = rel_temp - Kelvin

            m_value = str(temp)
            m_timestamp = datetime.datetime.now().strftime(
                '%Y-%m-%dT%H:%M:%S.%f'
            )

            LOG.info(m_value + " - " + m_timestamp)

            time.sleep(polling_time)
