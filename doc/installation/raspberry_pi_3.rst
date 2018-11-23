IoTronic Lightning-rod installation guide for Raspberry Pi 3
============================================================

We tested this procedure on a Raspberry Pi 3 board (Raspbian).


Install Lightning-rod
~~~~~~~~~~~~~~~~~~~~~

::

    pip3 install iotronic-lightningrod

Deployment
''''''''''

::
    lr_install


Iotronic setup
''''''''''''''

::
    lr_configure

Arguments required:
    <REGISTRATION-TOKEN> : token released by IoTronic registration procedure
    <WAMP-REG-AGENT-URL> : IoTronic Crossbar server URL

e.g.
::
    lr_configure 000001 ws(s)://<IOTRONIC-CROSSBAR-IP>:<IOTRONIC-CROSSBAR-PORT>/

Execution:
~~~~~~~~~~

::

    systemctl start lightning-rod.service

    tail -f /var/log/iotronic/lightning-rod.log