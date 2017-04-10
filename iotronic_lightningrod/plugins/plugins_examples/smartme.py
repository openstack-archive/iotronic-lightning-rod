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

from iotronic_lightningrod.plugins import Plugin
from iotronic_lightningrod.plugins import pluginApis as API

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

# User imports
import datetime
import json
import math
import threading
import time

# User global variables
ckan_addr = 'smartme-data.unime.it'
action_URL = "http://" + ckan_addr + "/api/3/action/datastore_upsert"
api_key = '22c5cfa7-9dea-4dd9-9f9d-eedf296852ae'
headers = {
    "Content-Type": "application/json",
    'Authorization': "" + api_key + ""
}

sensors_list = [
    'temperature',
    'brightness',
    'humidity',
    'pressure',
    'noise'
    # , 'gas'
]
position = None

SENSORS = {}

location = {}

device = API.getBoardGpio()

THR_KILL = None


# Sensors gloabl parameters

# Temperature Parameters
ADCres = 1023.0
Beta = 3950
Kelvin = 273.15
Rb = 10000
Ginf = 120.6685
latest_temp = None

# Noise Parameters
samples_number = 1000
amplitudes_sum = 0
amplitudes_count = 0


def Temperature():
    """To get Temperature value.

    :return: Temperature value (float)

    """
    try:
        voltage = device._readVoltage(SENSORS['temperature']['pin'])

        Rthermistor = float(Rb) * (float(ADCres) / float(voltage) - 1)
        rel_temp = float(Beta) / (math.log(float(Rthermistor) * float(Ginf)))
        temp = rel_temp - Kelvin

        # LOG.info("Temperature " + str(temp) + u" \u2103")

    except Exception as err:
        LOG.error("Error getting temperature: " + str(err))

    return temp


def Brightness():
    """To get Brightness value.

    :return: Brightness value (float)

    """
    try:
        voltage = float(device._readVoltage(SENSORS['brightness']['pin']))

        ldr = (2500 / (5 - voltage * float(0.004887)) - 500) / float(3.3)

        LOG.info("Brightness: " + str(ldr) + " (lux)")

    except Exception as err:
        LOG.error("Error getting brightness: " + str(err))

    return ldr


def Humidity():
    """To get Humidity value: this function uses the Temperature sensor too.

    :return: Humidity value (float)

    """
    try:

        degCelsius = Temperature()
        supplyVolt = float(4.64)
        HIH4030_Value = float(device._readVoltage(SENSORS['humidity']['pin']))
        voltage = HIH4030_Value / float(1023.) * supplyVolt
        sensorRH = float(161.0) * float(voltage) / supplyVolt - float(25.8)
        relHum = sensorRH / (float(1.0546) - float(0.0026) * degCelsius)

        LOG.info("Humidity " + str(relHum) + " percent")

    except Exception as err:
        LOG.error("Error getting humidity: " + str(err))

    return relHum


def Pressure():
    """To get Pressure value.

    :return: Pressure value (float)

    """
    try:

        in_pressure_raw = device.i2cRead('pressure')
        pressure = float(in_pressure_raw) * float(0.00025) * 10

        LOG.info("Pressure: " + str(pressure) + " hPa")

    except Exception as err:
        LOG.error("Error getting pressure: " + str(err))

    return pressure


def Noise():
    """To get Noise value.

    Elaborate a noise avarange value from noise listener.

    :return: Noise value (float)

    """

    try:

        global amplitudes_sum, amplitudes_count

        if amplitudes_count == float(0):
            amplitude = float(0)

        else:
            amplitude = float(amplitudes_sum / amplitudes_count)

        amplitudes_sum = 0
        amplitudes_count = 0

    except Exception as err:
        LOG.error("Error getting noise: " + str(err))

    return amplitude


def noise_listner():
    """Each two seconds collect a Noise sample.

    """

    global THR_KILL

    vect = []

    if THR_KILL:

        # LOG.info("listening noise..." + str(THR_KILL))

        for x in range(samples_number):

            read = float(device._readVoltage(SENSORS['noise']['pin']))
            vect.append(read)

        sorted_vect = sorted(vect)

        minimum = float(sorted_vect[50])
        maximum = float(sorted_vect[samples_number - 51])
        tmp_amplitude = float(maximum - minimum)

        global amplitudes_sum, amplitudes_count
        amplitudes_sum = float(amplitudes_sum + tmp_amplitude)
        amplitudes_count = float(amplitudes_count + 1)
        # LOG.info("amplitudes_sum = " + str(amplitudes_sum))
        # LOG.info("amplitudes_count = " + str(amplitudes_count))

        threading.Timer(2.0, noise_listner).start()

    else:
        LOG.debug("Cancelled SmartME noise listening: " + str(THR_KILL))


def getMetric(metric, ckan):
    """Function to get metric values.

    This function call the function relative to the 'metric'
    specified and if the 'ckan' flag is True we create the body for the
    REST request to send to CKAN database to store the sample there;

    :param metric: name of the metric analized: 'Temperature', etc
    :param ckan: flag True --> create JSON body for the CKAN request
    :return: ckan_data --> JSON data to send as request body to CKAN

    """

    # Call Sensors Metrics: Temperature(), etc...
    m_value = str(globals()[metric.capitalize()]())

    m_timestamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

    if metric == 'noise':
        LOG.info("Noise: " + str(m_value) + " amplitude")

    elif metric == 'temperature':
        LOG.info("Temperature " + str(m_value) + u" \u2103")

    if ckan:

        ckan_data = {}
        ckan_data["resource_id"] = str(SENSORS[metric]['ckanID'])
        ckan_data["method"] = "insert"
        ckan_data["records"] = []
        sample = {}
        sample["Latitude"] = location['latitude']
        sample["Longitude"] = location['longitude']
        sample["Altitude"] = location['altitude']
        metric_func_name = metric.capitalize()
        sample[metric_func_name] = m_value
        sample["Date"] = m_timestamp
        ckan_data["records"].append(sample)

        ckan_data = json.dumps(ckan_data)

    else:
        ckan_data = None

    return ckan_data


def getCKANdataset(board_uuid):
    """To get CKAN resource IDs for each metric type managed by SmartME boards.

    :param board_uuid:
    :return:

    """

    datasets_url = "http://" + ckan_addr + "/api/rest/dataset/" + board_uuid
    datasets = API.sendRequest(url=datasets_url, action='GET')
    ckan_data = json.loads(datasets)

    for resource in ckan_data['resources']:

        # LOG.info(resource['name'].capitalize())

        if resource['name'] in sensors_list:
            # LOG.debug(resource['name'])
            SENSORS[resource['name']]['ckanID'] = resource['id']
            # LOG.info(resource['name'] + " - " + resource['id'])


def setSensorsLayout(params):
    for sensor in sensors_list:
        SENSORS[sensor] = {}
        SENSORS[sensor]['pin'] = params[sensor]['pin']
        SENSORS[sensor]['enabled'] = params[sensor]['enabled']


def InitSmartMeBoard(params):
    """This function init the SmartME board.

    In the SmartME Arduino YUN board this function enables the needed
    devices and set the needed parameters about sensors and location.

    :param params: plugin parameters to configure the board.

    """

    # get location
    global location
    location = API.getLocation()
    LOG.info(
        "Board location: \n"
        + json.dumps(location, indent=4, separators=(',', ': '))
    )

    # set devices
    try:

        device.EnableI2c()
        device.EnableGPIO()

    except Exception as err:
        LOG.error("Error configuring devices: " + str(err))
        global THR_KILL
        THR_KILL = False

    # set up sensors
    setSensorsLayout(params)


class Worker(Plugin.Plugin):

    def __init__(self, uuid, name, q_result=None, params=None):
        super(Worker, self).__init__(
            uuid, name,
            q_result=q_result,
            params=params
        )

    def run(self):

        LOG.info("SmartME plugin starting...")

        global THR_KILL
        THR_KILL = self._is_running

        # Board initialization
        LOG.info("PARAMS list: " + str(self.params.keys()))

        if len(self.params.keys()) != 0:

            InitSmartMeBoard(self.params)

            # Get polling time
            polling_time = float(self.params['polling'])
            LOG.info("Polling time: " + str(polling_time))

            # GET CKAN SENSORS UUID
            getCKANdataset(API.getBoardID())

            LOG.info(
                "SENSORS: \n"
                + json.dumps(SENSORS, indent=4, separators=(',', ': '))
            )

            # START NOISE LISTENER if sensor enabled
            if SENSORS['noise']['enabled']:
                LOG.info("Starting noise listening...")
                noise_listner()

            LOG.info("CKAN enabled: " + str(self.params['ckan_enabled']))

            counter = 0

            while (self._is_running and THR_KILL):

                if sensors_list.__len__() != 0:

                    LOG.info("\n\n")

                    for sensor in sensors_list:

                        if SENSORS[sensor]['enabled']:

                            if self.params['ckan_enabled']:

                                API.sendRequest(
                                    url=action_URL,
                                    action='POST',
                                    headers=headers,
                                    body=getMetric(sensor, ckan=True),
                                    verbose=False
                                )

                            else:
                                getMetric(sensor, ckan=False)

                    counter = counter + 1
                    LOG.info("Samples sent: " + str(counter))

                    time.sleep(polling_time)

                else:
                    LOG.warning("No sensors!")
                    self._is_running = False
                    THR_KILL = self._is_running

            # Update the thread status: at this stage THR_KILL will be False
            THR_KILL = self._is_running

        else:
            LOG.error("No parameters provided!")
