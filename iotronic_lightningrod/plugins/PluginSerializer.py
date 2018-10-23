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

import _pickle as pickle

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class ObjectSerializer(object):
    """A PluginObject-aware Serializer.

    This implements the Oslo Serializer interface and provides the
    ability to serialize and deserialize PluginObject entities.
    Any service that needs to accept or return PluginObject as
    arguments or result values should pass this to its RpcProxy
    and RpcDispatcher objects.
    """

    def serialize_entity(self, entity):

        dumped = pickle.dumps(entity, 0)

        # LOG.debug(" - plugin serialized")

        return dumped

    def deserialize_entity(self, entity):

        loaded = pickle.loads(str.encode(entity))

        # LOG.debug(" - plugin deserialized")

        return loaded
