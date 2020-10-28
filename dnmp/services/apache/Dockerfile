ARG APACHE_VERSION
FROM ${APACHE_VERSION}

ARG CONTAINER_PACKAGE_URL

RUN if [ $CONTAINER_PACKAGE_URL ] ; then sed -i "s/dl-cdn.alpinelinux.org/${CONTAINER_PACKAGE_URL}/g" /etc/apk/repositories ; fi

RUN apk --no-cache add python3 py-yaml git make && \
    git clone https://github.com/devilbox/vhost-gen && \
    cd vhost-gen && \
    sed -i 's|/usr/bin/env python|/usr/bin/env python3|g' bin/vhost-gen && \
    make install

COPY ./vhost-gen/vhost-gen.py /usr/bin/vhost-gen

RUN chmod +x /usr/bin/vhost-gen

VOLUME ["/data/wwwroot", "/data/wwwlogs"]
VOLUME ["/usr/local/apache2/conf/vhost"]
