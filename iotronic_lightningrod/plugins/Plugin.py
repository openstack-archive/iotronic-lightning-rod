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

import abc
import six
import threading

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Plugin(threading.Thread):

    def __init__(self, uuid, name, q_result=None, params=None):

        threading.Thread.__init__(self)
        # self.setDaemon(1)
        self.setName("Plugin " + str(self.name))  # Set thread name
        LOG.debug("Plugin Name: " + self.name)

        self.uuid = uuid
        self.name = name
        self.status = "INITED"
        self.setStatus(self.status)
        self._is_running = True
        self.params = params
        self.q_result = q_result
        self.type = type

    @abc.abstractmethod
    def run(self):
        """RUN method where to implement the user's plugin logic

        """
    def stop(self):
        self._is_running = False

    def checkStatus(self):
        # LOG.debug("Plugin " + self.name + " check status: " + self.status)
        return self.status

    def setStatus(self, status):
        self.status = status
        # LOG.debug("Plugin " + self.name + " changed status: " + self.status)

    def complete(self, rpc_name, result):
        self.setStatus(result)
        result = rpc_name + " result: " + self.checkStatus()

        return result
