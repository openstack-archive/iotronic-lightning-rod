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

from datetime import datetime
import errno
import json
import os
import psutil
import signal
import subprocess
from urllib.parse import urlparse

from iotronic_lightningrod.modules import Module
from iotronic_lightningrod.modules import utils

import iotronic_lightningrod.wampmessage as WM

from oslo_config import cfg
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

CONF = cfg.CONF
SERVICES_CONF_FILE = CONF.lightningrod_home + "/services.json"


class ServiceManager(Module.Module):

    def __init__(self, board, session):
        super(ServiceManager, self).__init__("ServiceManager", board)

        self.wstun_ip = urlparse(board.wamp_config["url"])[1].split(':')[0]
        self.wstun_port = "8080"

        is_wss = False
        wurl_list = board.wamp_config["url"].split(':')
        if wurl_list[0] == "wss":
            is_wss = True

        if is_wss:
            self.wstun_url = "wss://" + self.wstun_ip + ":" + self.wstun_port
        else:
            self.wstun_url = "ws://" + self.wstun_ip + ":" + self.wstun_port

    def finalize(self):
        LOG.info("Cloud service tunnels to initialization:")

        # Load services.json configuration file
        services_conf = self._loadServicesConf()

        if len(services_conf['services']) != 0:

            wstun_process_list = []

            for p in psutil.process_iter():
                if len(p.cmdline()) != 0:
                    if (p.name() == "node" and "wstun" in p.cmdline()[1]):
                        wstun_process_list.append(p)

            for service_uuid in services_conf['services']:

                service_name = services_conf['services'][service_uuid]['name']
                service_pid = services_conf['services'][service_uuid]['pid']
                LOG.info(" - " + service_name)

                if len(wstun_process_list) != 0:

                    for wp in wstun_process_list:

                        if service_pid == wp.pid:
                            LOG.info(" --> the tunnel for '" + service_name +
                                     "' already exists; killing...")

                            # 1. Kill wstun process (if exists)
                            try:
                                os.kill(service_pid, signal.SIGKILL)
                                LOG.info(" --> service '" + service_name
                                         + "' with PID " + str(service_pid)
                                         + " was killed; creating new one...")
                            except OSError:
                                LOG.warning(" - WSTUN process already killed, "
                                            "creating new one...")

                            break

                # 2. Create the reverse tunnel
                public_port = \
                    services_conf['services'][service_uuid]['public_port']
                local_port = \
                    services_conf['services'][service_uuid]['local_port']

                wstun = self._startWstun(public_port, local_port)

                if wstun != None:
                    service_pid = wstun.pid

                    # 3. Update services.json file
                    services_conf['services'][service_uuid]['pid'] = \
                        service_pid
                    services_conf['services'][service_uuid]['updated_at'] = \
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

                    self._updateServiceConf(services_conf, service_uuid,
                                            output=True)

                    LOG.info(" --> Cloud service '" + service_name
                             + "' tunnel established.")
                else:
                    message = "Error spawning " + str(service_name) \
                              + " service tunnel!"
                    LOG.error(" - " + message)

        else:
            LOG.info(" --> No service tunnels to establish.")

    def restore(self):
        LOG.info("Cloud service tunnels to restore:")

        # Load services.json configuration file
        services_conf = self._loadServicesConf()

        if len(services_conf['services']) != 0:

            wstun_process_list = []

            # Collect all alive WSTUN proccesses
            for p in psutil.process_iter():
                if len(p.cmdline()) != 0:
                    if (p.name() == "node") and ("wstun" in p.cmdline()[1]):
                        wstun_process_list.append(p)

            for service_uuid in services_conf['services']:

                service_name = services_conf['services'][service_uuid]['name']
                service_pid = services_conf['services'][service_uuid]['pid']
                LOG.info(" - " + service_name)

                s_alive = False

                # WSTUN is still alive
                if len(wstun_process_list) != 0:

                    for wp in wstun_process_list:

                        if service_pid == wp.pid:
                            LOG.warning(" --> the tunnel for '" + service_name
                                        + "' is still established.")
                            s_alive = True
                            break

                if not s_alive:
                    # Create the reverse tunnel again
                    public_port = services_conf['services'][service_uuid]
                    ['public_port']
                    local_port = services_conf['services'][service_uuid]
                    ['local_port']

                    wstun = self._startWstun(public_port, local_port)

                    if wstun != None:
                        service_pid = wstun.pid

                        # 3. Update services.json file
                        services_conf['services'][service_uuid]['pid'] = \
                            service_pid
                        services_conf['services'][service_uuid]['updated_at'] = \
                            datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

                        self._updateServiceConf(services_conf,
                                                service_uuid, output=True)

                        LOG.info(" --> Cloud service '" + service_name
                                 + "' tunnel restored.")
                    else:
                        message = "Error spawning " + str(service_name) \
                                  + " service tunnel!"
                        LOG.error(" - " + message)

        else:
            LOG.info(" --> No service tunnels to restore.")

    def _loadServicesConf(self):
        """Load services.json JSON configuration.

        :return: JSON Services configuration

        """

        try:

            with open(SERVICES_CONF_FILE) as settings:
                services_conf = json.load(settings)

        except Exception as err:
            LOG.error(
                "Parsing error in " + SERVICES_CONF_FILE + ": " + str(err))
            services_conf = None

        return services_conf

    def _startWstun(self, public_port, local_port):

        opt_reverse = "-r" + str(
            public_port) + ":127.0.0.1:" + str(local_port)

        try:
            wstun = subprocess.Popen(
                ['/usr/bin/wstun', opt_reverse, self.wstun_url],
                stdout=subprocess.PIPE
            )
        except Exception as err:
            LOG.error("Error spawning WSTUN process: " + str(err))
            wstun = None

        return wstun

    def _updateServiceConf(self, services_conf, service_uuid, output=True):
        # Apply the changes to services.json
        with open(SERVICES_CONF_FILE, 'w') as f:
            json.dump(services_conf, f, indent=4)

            if output:
                LOG.info(" - service updated:\n" + json.dumps(
                    services_conf['services'][service_uuid],
                    indent=4,
                    sort_keys=True
                ))
            else:
                LOG.info(" - services.json file updated!")

    async def ServiceEnable(self, service, public_port):

        rpc_name = utils.getFuncName()

        service_name = service['name']
        service_uuid = service['uuid']
        local_port = service['port']

        LOG.info("RPC " + rpc_name + " CALLED for '" + service_name
                 + "' (" + service_uuid + ") service:")

        try:

            wstun = self._startWstun(public_port, local_port)

            if wstun != None:

                service_pid = wstun.pid

                LOG.debug(" - WSTUN stdout: " + str(wstun.stdout))

                # Update services.json file
                # Load services.json configuration file
                services_conf = self._loadServicesConf()

                # Save plugin settings in services.json
                if service_uuid not in services_conf['services']:

                    # It is a new plugin
                    services_conf['services'][service_uuid] = {}
                    services_conf['services'][service_uuid]['name'] = \
                        service_name
                    services_conf['services'][service_uuid]['public_port'] = \
                        public_port
                    services_conf['services'][service_uuid]['local_port'] = \
                        local_port
                    services_conf['services'][service_uuid]['pid'] = \
                        service_pid
                    services_conf['services'][service_uuid]['enabled_at'] = \
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                    services_conf['services'][service_uuid]['updated_at'] = ""

                else:
                    # The service was already added and we are updating it
                    services_conf['services'][service_uuid]['updated_at'] = \
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                    LOG.info(" - services.json file updated!")

                # Apply the changes to services.json
                self._updateServiceConf(services_conf, service_uuid,
                                        output=True)

                message = "Cloud service '" + str(service_name) \
                          + "' exposed on port " \
                          + str(public_port) + " on " + self.wstun_ip

                LOG.info(" - " + message + " with PID " + str(service_pid))

                w_msg = WM.WampSuccess(message)

            else:
                message = "Error spawning " + str(service_name) \
                          + " service tunnel!"
                LOG.error(" - " + message)
                w_msg = WM.WampError(message)

        except Exception as err:
            message = "Error exposing " + str(service_name) \
                      + " service: " + str(err)
            LOG.error(" - " + message)
            w_msg = WM.WampError(message)

        return w_msg.serialize()

    async def ServiceDisable(self, service):

        rpc_name = utils.getFuncName()

        service_name = service['name']
        service_uuid = service['uuid']

        LOG.info("RPC " + rpc_name
                 + " CALLED for '" + service_name
                 + "' (" + service_uuid + ") service:")

        # Remove from services.json file
        try:

            # Load services.json configuration file
            services_conf = self._loadServicesConf()

            if service_uuid in services_conf['services']:

                service_pid = services_conf['services'][service_uuid]['pid']

                try:

                    os.kill(service_pid, signal.SIGKILL)

                    message = "Cloud service '" \
                              + str(service_name) + "' tunnel disabled."

                    del services_conf['services'][service_uuid]

                    self._updateServiceConf(services_conf, service_uuid,
                                            output=False)

                    LOG.info(" - " + message)
                    w_msg = WM.WampSuccess(message)

                except Exception as err:
                    if err.errno == errno.ESRCH:  # ESRCH == No such process
                        message = "Service '" + str(
                            service_name) + "' WSTUN process is not running!"
                        LOG.warning(" - " + message)

                        del services_conf['services'][service_uuid]

                        self._updateServiceConf(services_conf, service_uuid,
                                                output=False)

                        w_msg = WM.WampWarning(message)

                    else:

                        message = "Error disabling '" + str(
                            service_name) + "' service tunnel: " + str(err)
                        LOG.error(" - " + message)
                        w_msg = WM.WampError(message)

            else:
                message = rpc_name + " result:  " + service_uuid \
                    + " already removed!"
                LOG.error(" - " + message)
                w_msg = WM.WampError(message)

        except Exception as err:
            message = "Updating services.json error: " + str(err)
            LOG.error(" - " + message)
            w_msg = WM.WampError(message)

        return w_msg.serialize()

    async def ServiceRestore(self, service, public_port):

        rpc_name = utils.getFuncName()

        service_name = service['name']
        service_uuid = service['uuid']

        LOG.info("RPC " + rpc_name
                 + " CALLED for '" + service_name
                 + "' (" + service_uuid + ") service:")

        # Load services.json configuration file
        services_conf = self._loadServicesConf()

        if service_uuid in services_conf['services']:

            local_port = \
                services_conf['services'][service_uuid]['local_port']
            service_pid = \
                services_conf['services'][service_uuid]['pid']

            try:

                # 1. Kill wstun process (if exists)
                try:
                    os.kill(service_pid, signal.SIGKILL)
                    LOG.info(" - service '" + service_name
                             + "' with PID " + str(service_pid)
                             + " was killed.")
                except OSError:
                    LOG.warning(" - WSTUN process already killed: "
                                "creating new one...")

                # 2. Create the reverse tunnel
                wstun = self._startWstun(public_port, local_port)

                if wstun != None:
                    service_pid = wstun.pid

                    # UPDATE services.json file
                    services_conf['services'][service_uuid]['pid'] = \
                        service_pid
                    services_conf['services'][service_uuid]['updated_at'] = \
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

                    self._updateServiceConf(services_conf, service_uuid,
                                            output=True)

                    message = "service " + str(service_name) \
                              + " restored on port " \
                              + str(public_port) + " on " + self.wstun_ip
                    LOG.info(" - " + message + " with PID " + str(service_pid))

                    w_msg = WM.WampSuccess(message)

                else:
                    message = "Error spawning " + str(service_name) \
                              + " service tunnel!"
                    LOG.error(" - " + message)
                    w_msg = WM.WampError(message)

            except Exception as err:
                message = "Error restoring '" + str(service_name) \
                          + "' service tunnel: " + str(err)
                LOG.error(" - " + message)
                w_msg = WM.WampError(message)

        else:

            local_port = service['port']

            wstun = self._startWstun(public_port, local_port)

            if wstun != None:

                service_pid = wstun.pid

                services_conf['services'][service_uuid] = {}
                services_conf['services'][service_uuid]['name'] = \
                    service_name
                services_conf['services'][service_uuid]['public_port'] = \
                    public_port
                services_conf['services'][service_uuid]['local_port'] = \
                    local_port
                services_conf['services'][service_uuid]['pid'] = \
                    service_pid
                services_conf['services'][service_uuid]['enabled_at'] = \
                    datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                services_conf['services'][service_uuid]['updated_at'] = ""

                self._updateServiceConf(services_conf, service_uuid,
                                        output=True)

                message = "service " + str(service_name) \
                          + " restored on port " \
                          + str(public_port) + " on " + self.wstun_ip
                LOG.info(" - " + message + " with PID " + str(service_pid))

                w_msg = WM.WampSuccess(message)

            else:
                message = "Error spawning " + str(service_name) \
                          + " service tunnel!"
                LOG.error(" - " + message)
                w_msg = WM.WampError(message)

        return w_msg.serialize()
