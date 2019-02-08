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
import queue
import signal
import socket
import subprocess
import time

import threading

from datetime import datetime
from threading import Thread
from urllib.parse import urlparse

from iotronic_lightningrod.config import package_path
from iotronic_lightningrod.modules import Module
from iotronic_lightningrod.modules import utils

import iotronic_lightningrod.wampmessage as WM

from iotronic_lightningrod import lightningrod
from random import randint

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


s_conf_FILE = CONF.lightningrod_home + "/services.json"


ws_server_alive = 0

global WS_MON_LIST
WS_MON_LIST = {}

global wstun_ip
wstun_ip = None
global wstun_port
wstun_port = None


class ServiceManager(Module.Module):

    def __init__(self, board, session):
        super(ServiceManager, self).__init__("ServiceManager", board)

        print("\nWSTUN bin path: " + str(CONF.services.wstun_bin))

        self.wstun_ip = urlparse(board.wamp_config["url"])[1].split(':')[0]
        self.wstun_port = "8080"

        global wstun_port
        wstun_port = self.wstun_port
        global wstun_ip
        wstun_ip = self.wstun_ip

        is_wss = False
        wurl_list = board.wamp_config["url"].split(':')
        if wurl_list[0] == "wss":
            is_wss = True

        if is_wss:
            self.wstun_url = "wss://" + self.wstun_ip + ":" + self.wstun_port
        else:
            self.wstun_url = "ws://" + self.wstun_ip + ":" + self.wstun_port

    def finalize(self):

        # Clean process table and remove zombies
        for _ in range(get_zombies()):
            try:
                os.waitpid(-1, os.WNOHANG)
            except Exception as exc:
                print(" - [finalize] Error cleaning" +
                      " wstun zombie process: " + str(exc))

        message = "WSTUN zombie processes cleaned."
        LOG.debug(message)
        print(message)

        LOG.info("Cloud service tunnels to initialization:")

        # Load services.json configuration file
        s_conf = self._loadServicesConf()

        if s_conf == None:

            LOG.error(" --> Error loading services.json file: " +
                      "backup is not restorable!")

            path_services_template = \
                package_path + "/templates/services.example.json"

            if os.path.isfile(path_services_template):

                LOG.info(" --> restoring services.json template")

                # Restore services.json template file
                os.system(
                    'cp ' + path_services_template + ' ' + s_conf_FILE
                )

                LOG.warn(" --> template restored: services configuration " +
                         "must be injected from Iotronic.")
            else:
                LOG.error(" --> services.json template does not exist!")

        else:

            print("WSTUN server checks:")

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(4)
            global ws_server_alive
            ws_server_alive = sock.connect_ex(
                (self.wstun_ip, int(self.wstun_port)))

            if ws_server_alive == 0:

                print(" - WSTUN server is online!")

                sock.close()  # close check socket

                if len(s_conf['services']) != 0:

                    wstun_process_list = []

                    try:
                        for p in psutil.process_iter():
                            if len(p.cmdline()) != 0:
                                if ((p.name() == "node") and (
                                    "wstun" in p.cmdline()[1]
                                )):
                                    wstun_process_list.append(p)
                    except Exception as e:
                        LOG.error(
                            " --> PSUTIL [finalize]: " +
                            "error getting wstun processes info: " + str(e)
                        )

                    if len(s_conf) != 0:
                        print("\nWSTUN processes:")

                    for s_uuid in s_conf['services']:

                        service_name = \
                            s_conf['services'][s_uuid]['name']
                        service_pid = \
                            s_conf['services'][s_uuid]['pid']
                        LOG.info(" - " + service_name)

                        if len(wstun_process_list) != 0:

                            for wp in wstun_process_list:

                                if service_pid == wp.pid:
                                    LOG.info(
                                        " --> the tunnel for '" + service_name
                                        + "' already exists; killing..."
                                    )

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

                                        try:
                                            os.waitpid(-1, os.WNOHANG)
                                            print(" - OLD wstun zombie "
                                                  "process cleaned.")
                                        except Exception as exc:
                                            print(
                                                " - [finalize] " +
                                                "Error cleaning old " +
                                                "wstun zombie process: " +
                                                str(exc)
                                            )

                                        LOG.info(
                                            " --> service '" + service_name
                                            + "' with PID " + str(service_pid)
                                            + " was killed; "
                                            + "creating new one...")

                                    except OSError:
                                        LOG.warning(
                                            " - WSTUN process already killed, "
                                            "creating new one...")

                                    break

                        # 2. Create the reverse tunnel
                        public_port = \
                            s_conf['services'][s_uuid]['public_port']
                        local_port = \
                            s_conf['services'][s_uuid]['local_port']

                        wstun = self._startWstunOnBoot(
                            public_port, local_port, event="boot")

                        if wstun != None:

                            service_pid = wstun.pid

                            # 3. Update services.json file
                            s_conf['services'][s_uuid]['pid'] = \
                                service_pid
                            s_conf['services'][s_uuid]['updated_at'] = \
                                datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

                            self._updateServiceConf(s_conf, s_uuid,
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

            else:
                sock.close()  # close check socket
                print(" - WSTUN server is offline!")
                LOG.error("WSTUN server is offline!")

    def restore(self):
        LOG.info("Cloud service tunnels to restore:")

        # Load services.json configuration file
        s_conf = self._loadServicesConf()

        if s_conf == None:

            LOG.error(" --> Error loading services.json file: "
                      "backup is not restorable!")

        else:

            if len(s_conf['services']) != 0:

                wstun_process_list = []

                # No zombie alert activation
                lightningrod.zombie_alert = False
                LOG.debug(
                    "[WSTUN-RESTORE] - Restore zombie_alert: "
                    + str(lightningrod.zombie_alert)
                )

                # Collect all alive WSTUN proccesses
                try:
                    for p in psutil.process_iter():
                        if (p.name() == "node"):
                            if (p.status() == psutil.STATUS_ZOMBIE):
                                LOG.warning("WSTUN ZOMBIE: " + str(p))
                                wstun_process_list.append(p)
                            elif ("wstun" in p.cmdline()[1]):
                                LOG.warning("WSTUN ALIVE: " + str(p))
                                wstun_process_list.append(p)

                                psutil.Process(p.pid).kill()
                                LOG.warning(" --> PID " + str(p.pid)
                                            + " killed!")
                except Exception as e:
                    LOG.error(
                        " --> PSUTIL [restore]: " +
                        "error getting wstun processes info: " + str(e)
                    )

                LOG.debug("[WSTUN-RESTORE] - WSTUN processes to restore:\n"
                          + str(wstun_process_list))

                for s_uuid in s_conf['services']:

                    Thread(
                        target=self._restoreWSTUN,
                        args=(s_conf, s_uuid,)
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

            try:

                for p in psutil.process_iter():
                    if len(p.cmdline()) == 0:
                        if ((p.name() == "node") and
                                (p.status() == psutil.STATUS_ZOMBIE)):
                            print(" - process: " + str(p))
                            zombie_list.append(p.pid)

            except Exception as e:
                LOG.error(
                    " --> PSUTIL [_zombie_hunter]: " +
                    "error getting wstun processes info. " +
                    "Please restore manually your services: " + str(e)
                )
                return

            if len(zombie_list) == 0:
                # print(" - no action required.")
                return

            print("\nCheck killed process...")
            print(" - Zombies found: " + str(zombie_list))

            # Load services.json configuration file
            s_conf = self._loadServicesConf()

            if s_conf == None:
                LOG.error(" --> Error loading services.json file: "
                          "backup is not restorable!")

            else:

                for s_uuid in s_conf['services']:

                    # Reload services.json file in order to check
                    # again if the PID was updated in the mean time
                    # by another zombie-hunter instance, before starting
                    # another instance of wstun
                    s_conf = self._loadServicesConf()

                    service_pid = s_conf['services'][s_uuid]['pid']

                    if service_pid in zombie_list:

                        message = "WSTUN zombie process ALERT!"
                        print(" - " + str(message))
                        LOG.debug("[WSTUN-RESTORE] --> " + str(message))

                        wstun_found = True

                        print(s_conf['services'][s_uuid])

                        service_public_port = \
                            s_conf['services'][s_uuid]['public_port']
                        service_local_port = \
                            s_conf['services'][s_uuid]['local_port']
                        service_name = \
                            s_conf['services'][s_uuid]['name']

                        try:

                            # Clean Zombie wstun process
                            try:
                                os.waitpid(-1, os.WNOHANG)
                                print(" - WSTUN zombie process cleaned.")
                            except Exception as exc:
                                print(" - [hunter] Error cleaning wstun " +
                                      "zombie process: " + str(exc))

                            wstun = self._startWstun(
                                service_public_port,
                                service_local_port,
                                event="zombie"
                            )

                            if wstun != None:

                                service_pid = wstun.pid

                                # UPDATE services.json file
                                s_conf['services'][s_uuid]['pid'] = \
                                    service_pid
                                s_conf['services'][s_uuid]['updated_at'] = \
                                    datetime.now().strftime(
                                        '%Y-%m-%dT%H:%M:%S.%f'
                                    )

                                self._updateServiceConf(
                                    s_conf,
                                    s_uuid,
                                    output=True
                                )

                                message = "Zombie service " \
                                          + str(service_name) \
                                          + " restored on port " \
                                          + str(service_public_port) \
                                          + " on " + self.wstun_ip

                                LOG.info(" - " + message
                                         + " with PID " + str(service_pid))
                            else:
                                message = "No need to spawn new tunnel for " \
                                          + str(service_local_port) + " port"
                                LOG.debug(message)
                                print(message)

                        except Exception:
                            pass

                        break

                if not wstun_found:
                    message = "Tunnel killed by LR"
                    print(" - " + str(message))
                    # LOG.debug("[WSTUN-RESTORE] --> " + str(message))

        else:
            print("\nWSTUN kill event:")
            message = "Tunnel killed by LR."
            print(" - " + str(message))

            # Clean zombie processes (no wstun)
            try:
                os.waitpid(-1, os.WNOHANG)
                print(" - Generic zombie process cleaned.")
            except Exception as exc:
                print(" - [hunter] Error cleaning "
                      "generic zombie process: " + str(exc))

            # LOG.debug("[WSTUN-RESTORE] --> " + str(message))
            # lightningrod.zombie_alert = True

    def _restoreWSTUN(self, s_conf, s_uuid):
        service_name = s_conf['services'][s_uuid]['name']
        service_pid = s_conf['services'][s_uuid]['pid']
        LOG.info(" - " + service_name)

        # Create the reverse tunnel again
        public_port = \
            s_conf['services'][s_uuid]['public_port']
        local_port = \
            s_conf['services'][s_uuid]['local_port']

        wstun = self._startWstun(public_port, local_port, event="restore")

        if wstun != None:
            service_pid = wstun.pid

            # 3. Update services.json file
            s_conf['services'][s_uuid]['pid'] = \
                service_pid
            s_conf['services'][s_uuid]['updated_at'] = \
                datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

            self._updateServiceConf(
                s_conf,
                s_uuid,
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

            with open(s_conf_FILE) as settings:
                s_conf = json.load(settings)

        except Exception as err:
            LOG.error(" --> Parsing error in " + s_conf_FILE + ": " + str(err))

            if os.path.isfile(s_conf_FILE):

                LOG.info(" --> restoring services.json file...")

                # Restore backup json file on error
                os.system(
                    'cp ' + s_conf_FILE + '.bkp ' + s_conf_FILE
                )

                try:
                    with open(s_conf_FILE) as settings:
                        s_conf = json.load(settings)
                except Exception as err:
                    LOG.error(" --> Parsing backup file error in " +
                              s_conf_FILE + ": " + str(err))
                    s_conf = None

            else:
                LOG.error(" --> services.json backup file does not exist!")
                s_conf = None

        return s_conf

    def _wstunMon(self, wstun, local_port):

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
                    LOG.info("WSTUN fd socket closed: " + str(event.pathname))
                    LOG.debug(
                        " - FD change notify:"
                        + "\nmethod: process_{}()\n"
                        + "file_path: {}\n"
                        + "event: {}\n".format(
                            method,
                            event.pathname,
                            event.maskname
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
        event_notifier.setName("TN-" + str(local_port))
        WS_MON_LIST[str(local_port)] = event_notifier

        watch_this = os.path.abspath(
            "/proc/" + str(wstun.pid) + "/fd/" + str(wstun_fd)
        )
        watch_manager.add_watch(watch_this, pyinotify.ALL_EVENTS)
        event_notifier.start()

    def _startWstun(self, public_port, local_port, event="no-set"):

        count_ws = 0
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4)

        global ws_server_alive
        ws_server_alive = sock.connect_ex(
            (self.wstun_ip, int(self.wstun_port))
        )

        while(ws_server_alive != 0 and count_ws < 5):
            count_ws = count_ws + 1
            LOG.warning(
                "WSTUN server is offline! Retry " + str(count_ws) + "/5..."
            )
            time.sleep(randint(3, 6))
            ws_server_alive = sock.connect_ex(
                (self.wstun_ip, int(self.wstun_port))
            )

        if ws_server_alive == 0:

            sock.close()  # close check socket

            opt_reverse = "-r" + str(public_port) + ":127.0.0.1:" + str(
                local_port)

            try:
                for p in psutil.process_iter():
                    if len(p.cmdline()) != 0:
                        if ((p.name() == "node") and
                                (str(local_port) in p.cmdline()[2])):
                            old_tun = p.cmdline()[2]
                            if old_tun == opt_reverse:
                                message = "[_startWstun] Tunnel for port " \
                                    + str(local_port) \
                                    + " already established!"
                                print(message)
                                LOG.warning(message)
                                return None

            except Exception as e:
                LOG.error(
                    " --> PSUTIL [_startWstun]: " +
                    "error getting wstun processes info: " + str(e)
                )

            try:

                wstun = subprocess.Popen(
                    [CONF.services.wstun_bin, opt_reverse, self.wstun_url],
                    stdout=subprocess.PIPE
                )

                if (event != "boot"):
                    print("WSTUN start event:")

                cmd_print = 'WSTUN exec: ' + str(CONF.services.wstun_bin) \
                            + opt_reverse + ' ' + self.wstun_url
                print(" - " + str(cmd_print))
                LOG.debug(cmd_print)

                # WSTUN MON
                # #############################################################

                try:
                    if event != "enable":
                        WS_MON_LIST[str(local_port)].stop()
                except Exception as err:
                    LOG.error("Error stopping WSTUN monitor: " + str(err))

                wsmon = Thread(
                    target=self._wstunMon,
                    name="THR-" + str(local_port),
                    args=(wstun, local_port, )
                )

                wsmon.start()

                # print(threading.enumerate())
                print(WS_MON_LIST)

                # #############################################################

            except Exception as err:
                LOG.error("Error spawning WSTUN process: " + str(err))
                wstun = None

        else:
            LOG.error("Error spawning WSTUN process: WSTUN server is offline!")
            wstun = None

        return wstun

    def _startWstunOnBoot(self, public_port, local_port, event="no-set"):

        opt_reverse = "-r" + str(public_port) + ":127.0.0.1:" + str(
            local_port)

        try:
            for p in psutil.process_iter():
                if len(p.cmdline()) != 0:
                    if ((p.name() == "node") and
                            (str(local_port) in p.cmdline()[2])):
                        old_tun = p.cmdline()[2]
                        if old_tun == opt_reverse:
                            message = "[_startWstunOnBoot] Tunnel for port " \
                                      + str(local_port) \
                                      + " already established!"
                            print(message)
                            LOG.warning(message)
                            return None

        except Exception as e:
            LOG.error(
                " --> PSUTIL [_startWstunOnBoot]: " +
                "error getting wstun processes info: " + str(e)
            )

        try:
            wstun = subprocess.Popen(
                [CONF.services.wstun_bin, opt_reverse, self.wstun_url],
                stdout=subprocess.PIPE
            )

            if (event != "boot"):
                print("WSTUN start event:")

            cmd_print = 'WSTUN exec: ' + str(CONF.services.wstun_bin) \
                        + opt_reverse + ' ' + self.wstun_url
            print(" - " + str(cmd_print))
            LOG.debug(cmd_print)

            # WSTUN MON
            # #############################################################

            wsmon = Thread(
                target=self._wstunMon,
                name="THR-" + str(local_port),
                args=(wstun, local_port,)
            )

            wsmon.start()

            # #############################################################

        except Exception as err:
            LOG.error("Error spawning WSTUN process: " + str(err))
            wstun = None

        return wstun

    async def ServicesStatus(self):
        rpc_name = utils.getFuncName()
        LOG.info("RPC " + rpc_name + " CALLED")

        thr_list = str(threading.enumerate())
        # print(WS_MON_LIST)
        print(thr_list + "\n" + str(WS_MON_LIST))

        w_msg = WM.WampSuccess(thr_list)

        return w_msg.serialize()

    def _updateServiceConf(self, s_conf, s_uuid, output=True):

        if s_conf == "":

            LOG.error(" - ERROR new services.json content is empty: " +
                      "Restoring backup.")

            # Restore backup json file on error
            os.system(
                'cp ' + s_conf_FILE + '.bkp ' + s_conf_FILE
            )

        else:

            # Apply the changes to services.json
            with open(s_conf_FILE, 'w') as f:
                json.dump(s_conf, f, indent=4)

                print(s_conf)

                if output:
                    LOG.info(" - service updated:\n" + json.dumps(
                        s_conf['services'][s_uuid],
                        indent=4,
                        sort_keys=True
                    ))
                else:
                    LOG.info(" - services.json file updated!")

            # Backup json file before update
            os.system(
                'cp ' + s_conf_FILE + ' ' + s_conf_FILE + '.bkp'
            )

    async def ServiceEnable(self, service, public_port):

        rpc_name = utils.getFuncName()

        service_name = service['name']
        s_uuid = service['uuid']
        local_port = service['port']

        LOG.info("RPC " + rpc_name + " CALLED for '" + service_name
                 + "' (" + s_uuid + ") service:")

        try:

            wstun = self._startWstun(public_port, local_port, event="enable")

            if wstun != None:

                service_pid = wstun.pid

                # Load services.json configuration file
                s_conf = self._loadServicesConf()

                if s_conf == None:
                    message = "Error loading services.json file: " \
                              + "backup is not restorable!"

                    LOG.error(" --> " + message)
                    w_msg = WM.WampError(message)

                else:

                    # Save plugin settings in services.json
                    if s_uuid not in s_conf['services']:

                        # It is a new plugin
                        s_conf['services'][s_uuid] = {}
                        s_conf['services'][s_uuid]['name'] = \
                            service_name
                        s_conf['services'][s_uuid]['public_port'] = \
                            public_port
                        s_conf['services'][s_uuid]['local_port'] = \
                            local_port
                        s_conf['services'][s_uuid]['pid'] = \
                            service_pid
                        s_conf['services'][s_uuid]['enabled_at'] = \
                            datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                        s_conf['services'][s_uuid]['updated_at'] = ""

                    else:
                        # The service was already added and we are updating it
                        s_conf['services'][s_uuid]['updated_at'] = \
                            datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                        LOG.info(" - services.json file updated!")

                    # Apply the changes to services.json
                    self._updateServiceConf(s_conf, s_uuid, output=True)

                    message = "Cloud service '" + str(service_name) \
                              + "' exposed on port " \
                              + str(public_port) + " on " + self.wstun_ip

                    LOG.info(" - " + message + " with PID " + str(service_pid))

                    w_msg = WM.WampSuccess(message)

            else:
                message = "Error spawning '" + str(service_name) \
                          + "' service tunnel!"
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
        s_uuid = service['uuid']

        LOG.info("RPC " + rpc_name
                 + " CALLED for '" + service_name
                 + "' (" + s_uuid + ") service:")

        # Remove from services.json file
        try:

            # Load services.json configuration file
            s_conf = self._loadServicesConf()

            if s_conf == None:
                LOG.error(" --> Error loading services.json file: "
                          "backup is not restorable!")

                message = "Error loading services.json file: " \
                          + "backup is not restorable!"
                LOG.error(" --> " + message)
                w_msg = WM.WampError(message)

            else:

                if s_uuid in s_conf['services']:

                    service_pid = \
                        s_conf['services'][s_uuid]['pid']

                    try:

                        # No zombie alert activation
                        lightningrod.zombie_alert = False

                        os.kill(service_pid, signal.SIGKILL)

                        message = "Cloud service '" \
                                  + str(service_name) + "' tunnel disabled."

                        del s_conf['services'][s_uuid]

                        self._updateServiceConf(s_conf, s_uuid,
                                                output=False)

                        LOG.info(" - " + message)

                        # Reactivate zombies monitoring
                        if not lightningrod.zombie_alert:
                            lightningrod.zombie_alert = True

                        w_msg = WM.WampSuccess(message)

                    except Exception as err:
                        if err.errno == errno.ESRCH:  # No such process
                            message = "Service '" + str(service_name) \
                                      + "' WSTUN process is not running!"
                            LOG.warning(" - " + message)

                            del s_conf['services'][s_uuid]

                            self._updateServiceConf(
                                s_conf,
                                s_uuid,
                                output=False
                            )

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
                    message = rpc_name + " result:  " + s_uuid \
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
        s_uuid = service['uuid']

        LOG.info("RPC " + rpc_name
                 + " CALLED for '" + service_name
                 + "' (" + s_uuid + ") service:")

        # Load services.json configuration file
        s_conf = self._loadServicesConf()

        if s_conf == None:

            message = "Error loading services.json file: " \
                      + "backup is not restorable!"
            LOG.error(" --> " + message)
            w_msg = WM.WampError(message)

        else:

            if s_uuid in s_conf['services']:

                local_port = \
                    s_conf['services'][s_uuid]['local_port']
                service_pid = \
                    s_conf['services'][s_uuid]['pid']

                try:

                    # No zombie alert activation
                    lightningrod.zombie_alert = False

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
                        s_conf['services'][s_uuid]['pid'] = \
                            service_pid
                        s_conf['services'][s_uuid]['updated_at'] = \
                            datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')

                        self._updateServiceConf(s_conf, s_uuid, output=True)

                        message = "service " + str(service_name) \
                                  + " restored on port " \
                                  + str(public_port) + " on " + self.wstun_ip
                        LOG.info(" - " + message
                                 + " with PID " + str(service_pid))

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

                    s_conf['services'][s_uuid] = {}
                    s_conf['services'][s_uuid]['name'] = \
                        service_name
                    s_conf['services'][s_uuid]['public_port'] = \
                        public_port
                    s_conf['services'][s_uuid]['local_port'] = \
                        local_port
                    s_conf['services'][s_uuid]['pid'] = \
                        service_pid
                    s_conf['services'][s_uuid]['enabled_at'] = \
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
                    s_conf['services'][s_uuid]['updated_at'] = ""

                    self._updateServiceConf(s_conf, s_uuid,
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


def get_zombies():
    # NOTE: don't use Popen() here
    output = os.popen(r"ps aux | grep ' Z' | grep -v grep").read()
    nzombies = len(output.splitlines())
    return nzombies


def services_list():

    try:

        s_list = ""

        with open(s_conf_FILE) as settings:
            s_conf = json.load(settings)

        for s_uuid in s_conf['services']:
            s_service = str(s_conf['services'][s_uuid]['name']) \
                + " - " + str(s_conf['services'][s_uuid]['public_port']) \
                + " - " + str(s_conf['services'][s_uuid]['local_port'])
            s_list = s_list + "<li>" + s_service + "</li>"

    except Exception as err:
        LOG.error("Error getting services list: " + str(err))
        s_list = str(err)

    return s_list


def wstun_status():

    if(wstun_ip != None) and (wstun_port != None):

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4)
        global ws_server_alive
        ws_server_alive = sock.connect_ex((wstun_ip, int(wstun_port)))
        sock.close()  # close check socket

    else:
        ws_server_alive = "N/A"

    return ws_server_alive
