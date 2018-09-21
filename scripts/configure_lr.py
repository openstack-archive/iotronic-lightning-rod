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

# !/usr/bin/python3
import os
import sys

if len(sys.argv) < 3:
    print('Arguments required: "<REGISTRATION-TOKEN> <WAMP-REG-AGENT-URL>',
          str(sys.argv))
else:
    os.system('sed -i "s|<REGISTRATION-TOKEN>|'
              + sys.argv[1] + '|g" /etc/iotronic/settings.json')
    os.system('sed -i "s|ws://<WAMP-SERVER>:<WAMP-PORT>/|'
              + sys.argv[2] + '|g" /etc/iotronic/settings.json')
    os.system('sed -i "s|<IOTRONIC-REALM>|s4t|g" /etc/iotronic/settings.json')
