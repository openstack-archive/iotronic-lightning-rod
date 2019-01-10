## Installation on arm architecture

GitHub repo:
- https://github.com/openstack/iotronic-lightning-rod

# Create container:
```
docker run -d --privileged \
-v lr_var:/var/lib/iotronic -v lr_le:/etc/letsencrypt/ \
-v lr_nginx:/etc/nginx -v lr_confs:/etc/iotronic/ \
--net=host --restart unless-stopped --name=lightning-rod mdslab/arm-openstack-iotronic-lightning-rod
```
