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

import os
import pkg_resources

dist = pkg_resources.get_distribution(__package__)
entry_points_name = \
    os.path.join(dist.location, dist.egg_name()) + ".egg-info/entry_points.txt"

# Iotronic python package folder
package_path = os.path.join(dist.location, __package__)
