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

import asyncio
import inspect
import pkg_resources
from six import moves
from stevedore import extension
import sys

from iotronic_lightningrod.config import entry_points_name
from iotronic_lightningrod.lightningrod import SESSION
from iotronic_lightningrod.modules import Module


from oslo_log import log as logging
LOG = logging.getLogger(__name__)


def getFuncName():
    return inspect.stack()[1][3]


def refresh_stevedore(namespace=None):
    """Trigger reload of entry points.

    Useful to have dynamic loading/unloading of stevedore modules.
    """
    # NOTE(sheeprine): pkg_resources doesn't support reload on python3 due to
    # defining basestring which is still there on reload hence executing
    # python2 related code.
    try:
        del sys.modules['pkg_resources'].basestring
    except AttributeError:
        # python2, do nothing
        pass
    # Force working_set reload
    moves.reload_module(sys.modules['pkg_resources'])
    # Clear stevedore cache
    cache = extension.ExtensionManager.ENTRY_POINT_CACHE
    if namespace:
        if namespace in cache:
            del cache[namespace]
    else:
        cache.clear()


class Utility(Module.Module):

    def __init__(self, board, session):
        super(Utility, self).__init__("Utility", board)

    def finalize(self):
        pass

    def restore(self):
        pass

    async def hello(self, client_name, message):
        import random
        s = random.uniform(0.5, 3.0)
        await asyncio.sleep(s)
        result = "Hello by board to Conductor " + client_name + \
                 " that said me " + message + " - Time: " + '%.2f' % s
        LOG.info("DEVICE hello result: " + str(result))

        return result

    async def plug_and_play(self, new_module, new_class):
        LOG.info("LR modules loaded:\n\t" + new_module)

        # Updating entry_points
        with open(entry_points_name, 'a') as entry_points:
            entry_points.write(
                new_module +
                '= iotronic_lightningrod.modules.' + new_module + ':'
                + new_class
            )

            # Reload entry_points
            refresh_stevedore('s4t.modules')
            LOG.info("New entry_points loaded!")

        # Reading updated entry_points
        named_objects = {}
        for ep in pkg_resources.iter_entry_points(group='s4t.modules'):
            named_objects.update({ep.name: ep.load()})

        await named_objects

        SESSION.disconnect()

        return str(named_objects)

    async def changeConf(self, conf):

        await self.board.getConf(conf)

        self.board.setUpdateTime()

        result = "Board configuration changed!"
        LOG.info("PROVISIONING RESULT: " + str(result))

        return result

    async def destroyNode(self, conf):

        await self.board.setConf(conf)

        result = "Board configuration cleaned!"
        LOG.info("DESTROY RESULT: " + str(result))

        return result
