IoTronic Lightning-rod installation guide for Ubuntu 16.04
==========================================================

We tested this procedure on a Ubuntu 16.04 (also within a LXD
container). Everything needs to be run as root.

Requirements
~~~~~~~~~~~~

* OS requirement

::

   apt install python3 python3-setuptools python3-pip gdb lsof libssl-dev libffi-dev

* NodeJS

::

  curl -sL https://deb.nodesource.com/setup_8.x | sudo -E bash -
  apt-get install -y nodejs
  npm install -g npm
  echo "NODE_PATH=/usr/lib/node_modules" | tee -a /etc/environment
  source /etc/environment > /dev/null


* WSTUN:

::

    npm install -g --unsafe @mdslab/wstun

* NGINX:

::

    apt install -y nginx
    sed -i 's/# server_names_hash_bucket_size 64;/server_names_hash_bucket_size 64;/g' /etc/nginx/nginx.conf
    sed -i "s|listen 80 default_server;|listen 50000 default_server;|g" /etc/nginx/sites-available/default
    sed -i "s|80 default_server;|50000 default_server;|g" /etc/nginx/sites-available/default


* Certbot

::
    add-apt-repository ppa:certbot/certbot
    apt update
    apt-get install python-certbot-nginx
    systemctl restart nginx


Install Lightning-rod
~~~~~~~~~~~~~~~~~~~~~
::

    pip3 install iotronic-lightningrod

Iotronic deployment
'''''''''''''''''''
::

    lr_install

Execution:
~~~~~~~~~~
::

    systemctl start lightning-rod.service

    tail -f /var/log/iotronic/lightning-rod.log

Iotronic setup
''''''''''''''
- Web-UI configuration:

::

    http://<BOARD-IP>:1474/config

Registration Agent URL: ws(s)://<IOTRONIC-CROSSBAR-IP>:<IOTRONIC-CROSSBAR-PORT>/
Registration Code: <REGISTRATION-CODE>


- Manual configuration (first registration only)

::

    lr_configure

Arguments required:
   * <REGISTRATION-CODE> , token released by IoTronic registration procedure
   * <WAMP-REG-AGENT-URL> , IoTronic Crossbar server WAMP URL:

   ws(s)://<IOTRONIC-CROSSBAR-IP>:<IOTRONIC-CROSSBAR-PORT>/

e.g.
::

    lr_configure <REGISTRATION-TOKEN> <WAMP-REG-AGENT-URL>

Troubleshooting:
~~~~~~~~~~~~~~~~
- **cbor error:** "Connection failed: RuntimeError: could not create serializer for "cbor"

   It is a dependency of Autobahn package

 **Solution:**
   pip3 install cborregistration only)