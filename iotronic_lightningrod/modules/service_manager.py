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

import errno
import json
import os
import psutil
import pyinotify
import signal
import subprocess
import time

from datetime import datetime
from threading import Thread
from urllib.parse import urlparse

from iotronic_lightningrod.modules import Module
from iotronic_lightningrod.modules import utils

import iotronic_lightningrod.wampmessage as WM

from iotronic_lightningrod import lightningrod


from oslo_config import cfg
from oslo_log import log as logging
LOG = logging.getLogger(__name__)


wstun_opts = [
    cfg.StrOpt(
        'wstun_bin',
        default='/usr/bin/wstun',
        help=('WSTUN bin for Services Manager')
    ),
]

CONF = cfg.CONF

service_group = cfg.OptGroup(
    name='services', title='Services options'
)
CONF.register_group(service_group)
CONF.register_opts(wstun_opts, group=service_group)


SERVICES_CONF_FILE = CONF.lightningrod_home + "/services.json"


class ServiceManager(Module.Module):

    def __init__(self, board, session):
        super(ServiceManager, self).__init__("ServiceManager", board)

        print("\nWSTUN bin path: " + str(CONF.services.wstun_bin))

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

            if len(services_conf) != 0:
                print("\nWSTUN processes:")

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

                            # No zombie alert activation
                            lightningrod.zombie_alert = False
                            LOG.debug(
                                "[WSTUN-RESTORE] - "
                                "on-finalize zombie_alert: " +
                                str(lightningrod.zombie_alert)
                            )

                            try:
                                os.kill(service_pid, signal.SIGINT)
                                print("OLD WSTUN KILLED: " + str(wp))
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

                wstun = self._startWstun(public_port, local_port, event="boot")

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

                signal.signal(signal.SIGCHLD, self._zombie_hunter)

            # Reactivate zombies monitoring
            if not lightningrod.zombie_alert:
                lightningrod.zombie_alert = True

        else:
            LOG.info(" --> No service tunnels to establish.")

            signal.signal(signal.SIGCHLD, self._zombie_hunter)

    def restore(self):
        LOG.info("Cloud service tunnels to restore:")

        # Load services.json configuration file
        services_conf = self._loadServicesConf()

        if len(services_conf['services']) != 0:

            wstun_process_list = []

            # No zombie alert activation
            lightningrod.zombie_alert = False
            LOG.debug("[WSTUN-RESTORE] - Restore zombie_alert: " + str(
                lightningrod.zombie_alert))

            # Collect all alive WSTUN proccesses
            for p in psutil.process_iter():
                if (p.name() == "node"):
                    if (p.status() == psutil.STATUS_ZOMBIE):
                        LOG.warning("WSTUN ZOMBIE: " + str(p))
                        wstun_process_list.append(p)
                    elif ("wstun" in p.cmdline()[1]):
                        LOG.warning("WSTUN ALIVE: " + str(p))
                        wstun_process_list.append(p)

                        psutil.Process(p.pid).kill()
                        LOG.warning(" --> PID " + str(p.pid) + " killed!")

            LOG.debug("[WSTUN-RESTORE] - WSTUN processes to restore:\n"
                      + str(wstun_process_list))

            for service_uuid in services_conf['services']:

                Thread(
                    target=self._restoreWSTUN,
                    args=(services_conf, service_uuid,)
                ).start()
                time.sleep(2)

            # Reactivate zombies monitoring
            if not lightningrod.zombie_alert:
                lightningrod.zombie_alert = True

        else:
            LOG.info(" --> No service tunnels to restore.")

    def _zombie_hunter(self, signum, frame):

        wstun_found = False

        if (lightningrod.zombie_alert):
            # print(signum); traceback.print_stack(frame)

            zombie_list = []

            for p in psutil.process_iter():
                if len(p.cmdline()) == 0:
                    if ((p.name() == "node") and
                            (p.status() == psutil.STATUS_ZOMBIE)):
                        print(" - process: " + str(p))
                        zombie_list.append(p.pid)

            if len(zombie_list) == 0:
                # print(" - no action required.")
                return

            print("\nCheck killed process...")
            print(" - Zombies found: " + str(zombie_list))

            # Load services.json configuration file
            services_conf = self._loadServicesConf()

            for service_uuid in services_conf['services']:

                service_pid = services_conf['services'][service_uuid]['pid']

                if service_pid in zombie_list:

                    message = "WSTUN zombie process ALERT!"
                    print(" - " + str(message))
                    LOG.debug("[WSTUN-RESTORE] --> " + str(message))

                    wstun_found = True

                    print(services_conf['services'][service_uuid])
                    service_public_port = \
                        services_conf['services'][service_uuid]['public_port']
                    service_local_port = \
                        services_conf['services'][service_uuid]['local_port']
                    service_name = \
                        services_conf['services'][service_uuid]['name']

                    try:

                        wstun = self._startWstun(
                            service_public_port,
                            service_local_port,
                            event="zombie"
                        )

                        if wstun != None:
                            service_pid = wstun.pid

                            # UPDATE services.json file
                            services_conf['services'][service_uuid]['pid'] = \
                                service_pid
                            services_conf['services'][service_uuid][
                                'updated_at'] = \
                                datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

                            self._updateServiceConf(services_conf,
                                                    service_uuid,
                                                    output=True)

                            message = "Zombie service " + str(service_name) \
                                      + " restored on port " \
                                      + str(service_public_port) \
                                      + " on " + self.wstun_ip
                            LOG.info(" - " + message + " with PID " + str(
                                service_pid))

                    except Exception:
                        pass

                    break

            if not wstun_found:
                message = "Tunnel killed by LR"
                print(" - " + str(message))
                # LOG.debug("[WSTUN-RESTORE] --> " + str(message))

        else:
            print("WSTUN kill event:")
            message = "Tunnel killed by LR"
            print(" - " + str(message))
            # LOG.debug("[WSTUN-RESTORE] --> " + str(message))
            # lightningrod.zombie_alert = True

    def _restoreWSTUN(self, services_conf, service_uuid):
        service_name = services_conf['services'][service_uuid]['name']
        service_pid = services_conf['services'][service_uuid]['pid']
        LOG.info(" - " + service_name)

        # Create the reverse tunnel again
        public_port = \
            services_conf['services'][service_uuid]['public_port']
        local_port = \
            services_conf['services'][service_uuid]['local_port']

        wstun = self._startWstun(public_port, local_port, event="restore")

        if wstun != None:
            service_pid = wstun.pid

            # 3. Update services.json file
            services_conf['services'][service_uuid]['pid'] = \
                service_pid
            services_conf['services'][service_uuid]['updated_at'] = \
                datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

            self._updateServiceConf(
                services_conf,
                service_uuid,
                output=True
            )

            LOG.info(" --> Cloud service '" + service_name
                     + "' tunnel restored.")
        else:
            message = "Error spawning " + str(service_name) \
                      + " service tunnel!"
            LOG.error(" - " + message)

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

    def _wstunMon(self, wstun):

        wfd_check = True

        while (wfd_check):
            try:

                wp = psutil.Process(int(wstun.pid))
                wstun_fd = wp.connections()[0].fd
                if len(wp.connections()) != 0:
                    LOG.debug("WSTUN alive socket: " + str(wp.connections()))
                wfd_check = False

            except IndexError as err:
                # LOG.error(str(err) + " - RETRY...")
                pass

            time.sleep(1)

        class EventProcessor(pyinotify.ProcessEvent):
            _methods = [
                # "IN_CREATE",
                # "IN_OPEN",
                # "IN_ACCESS",
                # "IN_ATTRIB",
                "IN_CLOSE_NOWRITE",
                "IN_CLOSE_WRITE",
                "IN_DELETE",
                "IN_DELETE_SELF",
                # "IN_IGNORED",
                # "IN_MODIFY",
                # "IN_MOVE_SELF",
                # "IN_MOVED_FROM",
                # "IN_MOVED_TO",
                # "IN_Q_OVERFLOW",
                # "IN_UNMOUNT",
                "default"
            ]

        def process_generator(cls, method):
            def _method_name(self, event):
                if(event.maskname == "IN_CLOSE_WRITE"):
                    LOG.info("WSTUN FD SOCKET CLOSED: " + str(event.pathname))
                    LOG.debug(
                        "\nMethod name: process_{}()\n"
                        "Path name: {}\n"
                        "Event Name: {}\n".format(
                            method, event.pathname, event.maskname
                        )
                    )

                    os.kill(wstun.pid, signal.SIGKILL)

            _method_name.__name__ = "process_{}".format(method)
            setattr(cls, _method_name.__name__, _method_name)

        for method in EventProcessor._methods:
            process_generator(EventProcessor, method)

        watch_manager = pyinotify.WatchManager()
        event_notifier = pyinotify.ThreadedNotifier(
            watch_manager, EventProcessor()
        )

        watch_this = os.path.abspath(
            "/proc/" + str(wstun.pid) + "/fd/" + str(wstun_fd)
        )
        watch_manager.add_watch(watch_this, pyinotify.ALL_EVENTS)
        event_notifier.start()

    def _startWstun(self, public_port, local_port, event="no-set"):

        opt_reverse = "-r" + str(public_port) + ":127.0.0.1:" + str(local_port)

        try:
            wstun = subprocess.Popen(
                [CONF.services.wstun_bin, opt_reverse, self.wstun_url],
                stdout=subprocess.PIPE
            )

            if(event != "boot"):
                print("WSTUN start event:")

            cmd_print = 'WSTUN exec: ' + str(CONF.services.wstun_bin) \
                        + opt_reverse + ' ' + self.wstun_url
            print(" - " + str(cmd_print))
            LOG.debug(cmd_print)

            # WSTUN MON
            # ##############################################################

            Thread(
                target=self._wstunMon,
                args=(wstun,)
            ).start()

            # self._wstunMon(wstun)

            # ##############################################################

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

            wstun = self._startWstun(public_port, local_port, event="enable")

            if wstun != None:

                service_pid = wstun.pid

                # LOG.debug(" - WSTUN stdout: " + str(wstun.stdout))

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

                    # No zombie alert activation
                    lightningrod.zombie_alert = False

                    """
                    LOG.debug(
                        "[WSTUN-RESTORE] - disable-RPC zombie_alert: "
                        + str(lightningrod.zombie_alert)
                    )
                    """

                    os.kill(service_pid, signal.SIGKILL)

                    message = "Cloud service '" \
                              + str(service_name) + "' tunnel disabled."

                    del services_conf['services'][service_uuid]

                    self._updateServiceConf(services_conf, service_uuid,
                                            output=False)

                    LOG.info(" - " + message)

                    # Reactivate zombies monitoring
                    if not lightningrod.zombie_alert:
                        lightningrod.zombie_alert = True

                    w_msg = WM.WampSuccess(message)

                except Exception as err:
                    if err.errno == errno.ESRCH:  # ESRCH == No such process
                        message = "Service '" + str(
                            service_name) + "' WSTUN process is not running!"
                        LOG.warning(" - " + message)

                        del services_conf['services'][service_uuid]

                        self._updateServiceConf(services_conf, service_uuid,
                                                output=False)

                        # Reactivate zombies monitoring
                        if not lightningrod.zombie_alert:
                            lightningrod.zombie_alert = True

                        w_msg = WM.WampWarning(message)

                    else:

                        message = "Error disabling '" + str(
                            service_name) + "' service tunnel: " + str(err)
                        LOG.error(" - " + message)

                        # Reactivate zombies monitoring
                        if not lightningrod.zombie_alert:
                            lightningrod.zombie_alert = True

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

                # No zombie alert activation
                lightningrod.zombie_alert = False
                """
                LOG.debug(
                    "[WSTUN-RESTORE] - restore-RPC lightningrod.zombie_alert: "
                    + str(lightningrod.zombie_alert))
                """

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
                wstun = self._startWstun(
                    public_port,
                    local_port,
                    event="kill-restore"
                )

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

                    # Reactivate zombies monitoring
                    if not lightningrod.zombie_alert:
                        lightningrod.zombie_alert = True

                    w_msg = WM.WampSuccess(message)

                else:
                    message = "Error spawning " + str(service_name) \
                              + " service tunnel!"
                    LOG.error(" - " + message)

                    # Reactivate zombies monitoring
                    if not lightningrod.zombie_alert:
                        lightningrod.zombie_alert = True

                    w_msg = WM.WampError(message)

            except Exception as err:
                message = "Error restoring '" + str(service_name) \
                          + "' service tunnel: " + str(err)
                LOG.error(" - " + message)
                w_msg = WM.WampError(message)

        else:

            local_port = service['port']

            wstun = self._startWstun(
                public_port,
                local_port,
                event="clean-restore"
            )

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
