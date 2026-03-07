FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y apt-transport-https wget gnupg curl

# Add Adoptium repo for Temurin 8 (OX 7.10.x requires Java 8)
RUN wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | \
        gpg --dearmor -o /etc/apt/trusted.gpg.d/adoptium.gpg && \
    echo "deb https://packages.adoptium.net/artifactory/deb bookworm main" \
        > /etc/apt/sources.list.d/adoptium.list

# Fetch the OX signing key used for current repos
RUN gpg --keyserver keyserver.ubuntu.com --recv-keys 12111537DFD4BCF6 && \
    gpg --export 12111537DFD4BCF6 | gpg --dearmor -o /etc/apt/trusted.gpg.d/open-xchange.gpg

ADD open-xchange.list /etc/apt/sources.list.d/open-xchange.list

RUN apt-get update && \
    apt-get install -y \
        temurin-8-jdk \
        mariadb-server \
        apache2 \
        open-xchange \
        open-xchange-authentication-database \
        open-xchange-grizzly \
        open-xchange-admin \
        open-xchange-appsuite \
        open-xchange-appsuite-backend \
        open-xchange-appsuite-manifest \
        open-xchange-dav

# Make Temurin 8 the default Java
RUN update-alternatives --set java /usr/lib/jvm/temurin-8-jdk-amd64/bin/java && \
    update-alternatives --set javac /usr/lib/jvm/temurin-8-jdk-amd64/bin/javac

ADD proxy_http.conf /etc/apache2/conf-available/proxy_http.conf
ADD open-xchange /etc/apache2/sites-enabled/000-default.conf

RUN a2enmod proxy proxy_http proxy_balancer lbmethod_byrequests expires \
    deflate headers rewrite mime setenvif && \
    a2enconf proxy_http.conf

RUN mkdir -p -m 0777 /ox /ox/store && \
    chown open-xchange:open-xchange /ox/store

ADD run.sh /ox/run.sh
RUN chmod +x /ox/run.sh

EXPOSE 80

CMD ["/ox/run.sh"]
