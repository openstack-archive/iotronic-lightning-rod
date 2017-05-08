IoTronic Lightning-rod installation guide for Ubuntu 16.04
==========================================================

We tested this procedure on a Ubuntu 16.04 (also within a LXD
container). Everything needs to be run as root.

Install from source code via Git
--------------------------------

Install requirements
~~~~~~~~~~~~~~~~~~~~

::

    pip install oslo-config oslo_log twisted autobahn httplib2

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
    cp etc/systemd/system/s4t-lightning-rod.service /etc/systemd/system/lightning-rod.service
    chmod +x /etc/systemd/system/lightning-rod.service
    systemctl daemon-reload

-  Edit configuration file:

   -  nano /var/lib/iotronic/settings.json

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

-  setup logrotate:
-  nano /etc/logrotate.d/lightning-rod.log

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

    systemctl restart lightning-rod.service

    tail -f /var/log/iotronic/lightning-rod.log