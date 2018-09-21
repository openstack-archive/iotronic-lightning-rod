# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# THIS FILE IS MANAGED BY THE GLOBAL REQUIREMENTS REPO - DO NOT EDIT
import setuptools

# In python < 2.7.4, a lazy loading of package `pbr` will break
# setuptools if some other modules registered functions in `atexit`.
# solution from: http://bugs.python.org/issue15881#msg170215
try:
    import multiprocessing  # noqa
except ImportError:
    pass

setuptools.setup(
    setup_requires=['pbr>=1.8'],
    pbr=True,
    include_package_data=True,
    data_files=[
        ('/iotronic_lightningrod/etc/iotronic',
         ['etc/iotronic/iotronic.conf']),
        ('/iotronic_lightningrod/scripts', ['scripts/install_lr.py']),
        ('/iotronic_lightningrod/scripts', ['scripts/configure_lr.py']),
        ('/iotronic_lightningrod/templates',
         ['templates/settings.example.json']),
        ('/iotronic_lightningrod/templates',
         ['templates/plugins.example.json']),
        ('/iotronic_lightningrod/templates',
         ['templates/services.example.json']),
        ('/iotronic_lightningrod/etc/logrotate.d',
         ['etc/logrotate.d/lightning-rod.log']),
        ('/iotronic_lightningrod/etc/systemd/system/',
         ['etc/systemd/system/s4t-lightning-rod.service']),
    ],
)
