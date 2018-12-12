IoTronic Lightning-rod installation guide for Ubuntu 16.04
==========================================================

We tested this procedure on a Ubuntu 16.04 (also within a LXD
container). Everything needs to be run as root.

Install Lightning-rod
~~~~~~~~~~~~~~~~~~~~~
::

    pip3 install iotronic-lightningrod

Iotronic deployment
'''''''''''''''''''
::

    lr_install


Iotronic setup
''''''''''''''
::

    lr_configure

Arguments required:
   * <REGISTRATION-TOKEN> , token released by IoTronic registration procedure
   * <WAMP-REG-AGENT-URL> , IoTronic Crossbar server WAMP URL:
   ws(s)://<IOTRONIC-CROSSBAR-IP>:<IOTRONIC-CROSSBAR-PORT>/

e.g.
::

    lr_configure <REGISTRATION-TOKEN> <WAMP-REG-AGENT-URL>

Execution:
~~~~~~~~~~
::

    systemctl start lightning-rod.service

    tail -f /var/log/iotronic/lightning-rod.log
