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
import subprocess
import sys


def LR_restart():
    try:
        LOG.warning("Lightning-rod RESTARTING...")
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception as err:
        LOG.error("Lightning-rod restarting error" + str(err))


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
        print("WAMP RECOVERY: " + str(proc.connections()[0]))

        ws_fd = proc.connections()[0].fd
        first = b"call shutdown("
        fd = str(ws_fd).encode('ascii')
        last = b"u,0)\nquit\ny"
        commands = b"%s%s%s" % (first, fd, last)
        process.communicate(input=commands)[0]

        msg = "Websocket-Zombie closed! Restoring..."
        LOG.warning(msg)
        print(msg)

    except Exception as e:
        LOG.warning("RPC-ALIVE - destroyWampSocket error: " + str(e))


def get_version(package):
    package = package.lower()
    return next((p.version for p in pkg_resources.working_set if
                 p.project_name.lower() == package), "No version")
