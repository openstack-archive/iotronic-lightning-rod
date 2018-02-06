# Copyright 2017 MDSLAB - University of Messina
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

__author__ = "Nicola Peditto <npeditto@unime.it"

import json

SUCCESS = 'SUCCESS'
ERROR = 'ERROR'
WARNING = 'WARNING'


def deserialize(received):
    m = json.loads(received)
    return WampMessage(**m)


class WampMessage(object):
    def __init__(self, message=None, result=None):
        self.message = message
        self.result = result

    def serialize(self):
        return json.dumps(self, default=lambda o: o.__dict__)
    """
    def deserialize(self, received):
        self.__dict__ = json.loads(received)
        return self
    """


class WampSuccess(WampMessage):
    def __init__(self, msg=None):
        super(WampSuccess, self).__init__(msg, SUCCESS)


class WampError(WampMessage):
    def __init__(self, msg=None):
        super(WampError, self).__init__(msg, ERROR)


class WampWarning(WampMessage):
    def __init__(self, msg=None):
        super(WampWarning, self).__init__(msg, WARNING)
