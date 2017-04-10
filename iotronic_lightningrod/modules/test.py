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


from autobahn.twisted.util import sleep
from iotronic_lightningrod.modules import Module
from twisted.internet.defer import returnValue

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class Test(Module.Module):

    def __init__(self, board):

        super(Test, self).__init__("Test", board)

    def test_function(self):
        import random
        s = random.uniform(0.5, 1.5)
        yield sleep(s)
        result = "DEVICE test result: TEST!"
        LOG.info(result)
        returnValue(result)

    def add(self, x, y):
        c = yield x + y
        LOG.info("DEVICE add result: " + str(c))
        returnValue(c)
