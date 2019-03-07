# Copyright 2018 MDSLAB - University of Messina
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

__author__ = "Nicola Peditto <n.peditto@gmail.com>"


from oslo_log import log as logging
LOG = logging.getLogger(__name__)


import os
import pkg_resources
import psutil
import site
import subprocess
import sys
import threading
import time


def LR_restart():
    try:
        LOG.warning("Lightning-rod RESTARTING...")
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception as err:
        LOG.error("Lightning-rod restarting error" + str(err))


def LR_restart_delayed(seconds):

    def delayLRrestarting():
        time.sleep(seconds)
        python = sys.executable
        os.execl(python, python, *sys.argv)

    threading.Thread(target=delayLRrestarting).start()


def checkIotronicConf(lr_CONF):

    try:
        if(lr_CONF.log_file == None):
            LOG.warning("'log_file' is not specified!")
            return False
        else:
            print("View logs in " + lr_CONF.log_file)
            return True
    except Exception as err:
        print(err)
        return False


def destroyWampSocket():

    LR_PID = os.getpid()

    try:

        process = subprocess.Popen(
            ["gdb", "-p", str(LR_PID)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

        proc = psutil.Process()

        conn_list = proc.connections()
        proc_msg = "WAMP RECOVERY: " + str(conn_list)
        print(proc_msg)
        LOG.info(proc_msg)

        wamp_conn_set = False

        for socks in conn_list:
            # print(socks.raddr, socks.fd)
            if socks.raddr != ():
                # print(socks.raddr.port, socks.fd)
                if socks.raddr.port == 8181:
                    socks_msg = "FD selected: " + str(socks.fd) \
                                + " [port " + str(socks.raddr.port) + "]"

                    print(socks_msg)
                    LOG.info(socks_msg)

                    ws_fd = socks.fd
                    first = b"call ((void(*)()) shutdown)("
                    fd = str(ws_fd).encode('ascii')
                    last = b"u,0)\nquit\ny"
                    commands = b"%s%s%s" % (first, fd, last)
                    process.communicate(input=commands)[0]

                    msg = "Websocket-Zombie closed! Restoring..."
                    LOG.warning(msg)
                    print(msg)
                    # WAMP connection found!
                    wamp_conn_set = True
                    # LOG.info("WAMP CONNECTION FOUND")

        if wamp_conn_set == False:
            LOG.warning("WAMP CONNECTION NOT FOUND: LR restarting...")
            # In conn_list there is not the WAMP connection!
            LR_restart()

    except Exception as e:
        LOG.warning("RPC-ALIVE - destroyWampSocket error: " + str(e))
        LR_restart()


def get_version(package):
    package = package.lower()
    return next((p.version for p in pkg_resources.working_set if
                 p.project_name.lower() == package), "No version")


def get_socket_info(wport):

    lr_mac = "N/A"

    try:
        for socks in psutil.Process().connections():
            if len(socks.raddr) != 0:
                if (socks.raddr.port == wport):
                    lr_net_iface = socks
                    print("WAMP SOCKET: " + str(lr_net_iface))
                    dct = psutil.net_if_addrs()
                    for key in dct.keys():
                        if isinstance(dct[key], dict) == False:
                            iface = key
                            for elem in dct[key]:
                                ip_addr = elem.address
                                if ip_addr == str(
                                        lr_net_iface.laddr.ip):
                                    for snicaddr in dct[iface]:
                                        if snicaddr.family == 17:
                                            lr_mac = snicaddr.address
                                            return [iface, ip_addr, lr_mac]

    except Exception as e:
        LOG.warning("Error getting socket info " + str(e))
        lr_mac = "N/A"
        return lr_mac

    return lr_mac


def backupConf():
    try:
        os.system(
            'cp /etc/iotronic/settings.json /etc/iotronic/settings.json.bkp'
        )
    except Exception as e:
        LOG.warning("Error restoring configuration " + str(e))


def restoreConf():
    try:
        result = os.system(
            'cp /etc/iotronic/settings.json.bkp /etc/iotronic/settings.json'
        )
    except Exception as e:
        LOG.warning("Error restoring configuration " + str(e))
        result = str(e)

    return result


def restoreFactoryConf():
    try:
        py_dist_pack = site.getsitepackages()[0]
        os.system(
            'cp ' + py_dist_pack + '/iotronic_lightningrod/'
            + 'templates/settings.example.json '
            + '/etc/iotronic/settings.json'
        )
    except Exception as e:
        LOG.warning("Error restoring configuration " + str(e))
