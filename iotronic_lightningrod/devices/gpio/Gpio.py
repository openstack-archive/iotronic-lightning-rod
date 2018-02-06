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

__author__ = "Nicola Peditto <npeditto@unime.it"

import abc
import six

from oslo_log import log as logging

LOG = logging.getLogger(__name__)

from iotronic_lightningrod.config import package_path


@six.add_metaclass(abc.ABCMeta)
class Gpio(object):
    def __init__(self, name):
        self.name = name
        self.path = package_path + "/gpio/" + self.name + ".py"

    @abc.abstractmethod
    def EnableGPIO(self):
        """Enable reading and writing functionalities of the GPIO module

        :return: status of the operation (String)
        """

    @abc.abstractmethod
    def DisableGPIO(self):
        """Disable reading and writing functionalities of the GPIO module

        :return: status of the operation (String)
        """
