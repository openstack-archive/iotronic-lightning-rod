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

import signal

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

from iotronic_lightningrod.common import utils


def manageTimeout(error_message, action):
    try:

        raise TimeoutError(error_message, action)

    except TimeoutError as err:
        details = err.args[0]
        if (action == "ws_alive"):

            LOG.warning("Iotronic RPC-ALIVE timeout details: " + str(details))
            try:

                utils.destroyWampSocket()

            except Exception as e:
                LOG.warning("Iotronic RPC-ALIVE timeout error: " + str(e))

        else:
            LOG.warning("Board connection call timeout ["
                        + str(action) + "]: " + str(details))
            utils.LR_restart()


class NginxError(Exception):

    def __init__(self, message):
        super(NginxError, self).__init__(message)


class TimeoutError(Exception):

    def __init__(self, message, action):
        super(TimeoutError, self).__init__(message)

        self.action = action


class timeout(object):

    def __init__(self, seconds=1, error_message='Timeout', action=None):
        self.seconds = seconds
        self.error_message = error_message
        self.action = action

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message, self.action)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


class timeoutRPC(object):

    def __init__(self, seconds=1, error_message='Timeout-RPC', action=None):
        self.seconds = seconds
        self.error_message = error_message
        self.action = action

    def handle_timeout(self, signum, frame):
        manageTimeout(self.error_message, self.action)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


class timeoutALIVE(object):

    def __init__(self, seconds=1, error_message='Timeout-Alive', action=None):
        self.seconds = seconds
        self.error_message = error_message
        self.action = action

    def handle_timeout(self, signum, frame):
        manageTimeout(self.error_message, self.action)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)
