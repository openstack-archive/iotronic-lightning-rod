## Installation on arm architecture

GitHub repo:
- https://github.com/openstack/iotronic-lightning-rod

# Configure Lightning-rod environment

* Create the folder in your system to store Lightning-rod settings  <LR_CONF_PATH> (e.g. "/etc/iotronic/"):
```
sudo mkdir  <LR_CONF_PATH>
```
 
* Get Lightning-rod configuration template files:
```
cd  <LR_CONF_PATH>
sudo wget https://raw.githubusercontent.com/openstack/iotronic-lightning-rod/master/templates/settings.example.json -O settings.json
sudo wget https://raw.githubusercontent.com/openstack/iotronic-lightning-rod/master/etc/iotronic/iotronic.conf
```

* Configure Lightning-rod identity:
```
cd  <LR_CONF_PATH>
wget https://raw.githubusercontent.com/openstack/iotronic-lightning-rod/master/scripts/lr_configure
chmod +x lr_configure
./lr_configure -c <REGISTRATION-TOKEN> <WAMP-REG-AGENT-URL>  <LR_CONF_PATH>
```

# Create container:
```
docker run -d --privileged \
-v lr_var:/var/lib/iotronic -v lr_le:/etc/letsencrypt/ \
-v  <LR_CONF_PATH>/settings.json:/etc/iotronic/settings.json \
-v  <LR_CONF_PATH>/iotronic.conf:/etc/iotronic/iotronic.conf \
--net=host --restart unless-stopped \
--name=lightning-rod mdslab/rpi-openstack-iotronic-lightning-rod
```
