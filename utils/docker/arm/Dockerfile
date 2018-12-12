FROM ubuntu:bionic

RUN  apt-get update && apt-get install -y \
 socat dsniff git ntpdate python build-essential vim lsof gdb screen python3 python3-setuptools python3-pip npm

ENV TZ 'Europe/Rome'
ENV DEBIAN_FRONTEND=noninteractive
RUN echo $TZ > /etc/timezone && apt-get update && apt-get install -y tzdata && rm -f /etc/localtime && ln -nfs /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

RUN apt-get install -y nginx python-certbot-nginx
RUN sed -i 's/# server_names_hash_bucket_size 64;/server_names_hash_bucket_size 64;/g' /etc/nginx/nginx.conf

RUN rm -rf /var/lib/apt/lists/*

RUN npm install -g --unsafe @mdslab/wstun@1.0.9 && npm cache --force clean

RUN pip3 install iotronic-lightningrod

COPY data/lr_install /usr/local/bin/lr_install
COPY data/startLR /usr/local/bin/startLR

RUN /usr/local/bin/lr_install

VOLUME /var/lib/iotronic

RUN ln -s /usr/local/bin/wstun /usr/bin/wstun

#CMD [ "/usr/sbin/nginx"]
#CMD [ "/usr/local/bin/lightning-rod"]
CMD ["/usr/local/bin/startLR"]
