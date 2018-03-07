IoTronic Lightning-rod installation guide for Arduino YUN
=========================================================

We tested this procedure on a Arduino YUN board with OpenWRT LininoIO image.

Install from source code
------------------------

Install requirements
~~~~~~~~~~~~~~~~~~~~

Install Python and PIP:
'''''''''''''''''''''''

::

    opkg update
    opkg install python-setuptools
    easy_install pip

Install dependencies
''''''''''''''''''''

::

    opkg install git bzip2 python-netifaces
    pip install --no-cache-dir zope.interface pyserial Babel oslo.config
    oslo.log
    easy_install httplib2

Install Autobahn:
'''''''''''''''''

::

    easy_install autobahn

Set up environment:
~~~~~~~~~~~~~~~~~~~

::

    mkdir -p /var/lib/iotronic
    mkdir /var/lib/iotronic/plugins
    mkdir /var/log/iotronic/
    mkdir /etc/iotronic

Install Lightning-rod
~~~~~~~~~~~~~~~~~~~~~

Get source code
'''''''''''''''

::

    cd /var/lib/iotronic
    git clone git://github.com/MDSLab/iotronic-lightning-rod-agent.git
    mv iotronic-lightning-rod-agent/ iotronic-lightning-rod/

Deployment
''''''''''

::

    cd iotronic-lightning-rod/
    cp etc/iotronic/iotronic.conf  /etc/iotronic/
    cp settings.example.json /var/lib/iotronic/settings.json
    cp plugins.example.json /var/lib/iotronic/plugins.json
    cp services.example.json /var/lib/iotronic/services.json
    cp etc/init.d/lightning-rod /etc/init.d/lightning-rod
    chmod +x /etc/init.d/lightning-rod
    touch /var/log/iotronic/lightning-rod.log

-  Edit configuration file:

nano /var/lib/iotronic/settings.json

::

    {
     "iotronic": {
       "board": {
         "token": "<REGISTRATION-TOKEN>"
       },
       "wamp": {
         "registration-agent": {
           "url": "ws://<WAMP-SERVER>:<WAMP-PORT>/",
           "realm": "<IOTRONIC-REALM>"
         }
       }
     }
    }

-  Set up logrotate:

nano /etc/logrotate.d/lightning-rod.log

::

    /var/log/iotronic/lightning-rod.log {
        weekly
        rotate = 3
        compress
        su root root
        maxsize 5M
    }

Building
''''''''

::

    cd /var/lib/iotronic/iotronic-lightning-rod/
    python setup.py install

Execution:
~~~~~~~~~~

::

    /etc/init.d/lightning-rod restart

    tail -f /var/log/iotronic/lightning-rod.log