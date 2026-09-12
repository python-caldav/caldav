# Bedework 5 CalDAV test server.
#
# There is no usable public image for a current Bedework, and the upstream
# source is spread over ~20 git repositories that are assembled into a Wildfly
# galleon feature pack.  Rather than building that from master we install the
# released feature pack the way upstream tells deployers to:
# https://bedework.github.io/bedework/#featurepack-install
#
# Override BW_VERSION to test another release, or BW_LAYERS to install a
# smaller subset (bw-democaluser-h2 is calendaring only, no public events).

# ApacheDS - the demo system's LDAP server - cannot run on JDK 21; see
# apacheds-setenv.sh.  Everything else does, so carry a second runtime rather
# than downgrade the whole image.
FROM docker.io/library/eclipse-temurin:17-jre AS jre17

FROM docker.io/library/eclipse-temurin:21-jdk

ARG GALLEON_VERSION=6.1.0.Final
ARG BW_VERSION=5.0.0
ARG BW_LAYERS=bw-demoall-h2,web-console

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl unzip procps && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash bedework

USER bedework
WORKDIR /home/bedework

# Galleon resolves ~950 artifacts from Maven Central into ~/.m2 on the way to
# building the wildfly tree; drop the cache and the installer again in the same
# layer so they never reach the image.
RUN curl -sSLo galleon.zip \
        "https://github.com/wildfly/galleon/releases/download/${GALLEON_VERSION}/galleon-${GALLEON_VERSION}.zip" && \
    unzip -q galleon.zip && \
    "./galleon-${GALLEON_VERSION}/bin/galleon.sh" install \
        "org.bedework.deploy:bw-wf-feature-pack:${BW_VERSION}" \
        --dir=/home/bedework/wildfly --verbose --layers="${BW_LAYERS}" && \
    rm -rf galleon.zip "galleon-${GALLEON_VERSION}" /home/bedework/.m2

# The feature pack ships H2 1.4.x demo databases alongside an H2 2.x driver
# that cannot read them; see migrate-h2.sh.
ARG H2_LEGACY_VERSION=1.4.197
COPY --chown=bedework:bedework migrate-h2.sh /tmp/migrate-h2.sh
RUN /tmp/migrate-h2.sh "${H2_LEGACY_VERSION}" && rm -f /tmp/migrate-h2.sh

# Upstream ships /cal on a module that cannot load a class the shared calendar
# service needs, and the resulting failure poisons /ucaldav too; see
# patch-modules.sh.
COPY --chown=bedework:bedework patch-modules.sh /tmp/patch-modules.sh
RUN /tmp/patch-modules.sh && rm -f /tmp/patch-modules.sh

# OpenSearch's disk watermarks are about protecting a production cluster from
# the host filling up.  Here they only mean that a busy developer machine turns
# every write into "index has read-only-allow-delete block" and every PUT into
# a 500 - the test data is a few hundred kB.
RUN printf '\n# Disposable test server: do not police the host filesystem.\ncluster.routing.allocation.disk.threshold_enabled: false\n' \
        >> /home/bedework/wildfly/opensearch/config/opensearch.yml

COPY --from=jre17 /opt/java/openjdk /opt/java/jdk17
COPY --chown=bedework:bedework apacheds-setenv.sh /home/bedework/wildfly/apacheds/bin/setenv.sh

ENV JBOSS_HOME=/home/bedework/wildfly
# bwstartwildfly.sh passes this straight to standalone.sh; without it wildfly
# binds to loopback and the published port is dead.
ENV JBOSS_BIND="-b 0.0.0.0"

COPY --chown=bedework:bedework run.sh /home/bedework/run.sh

EXPOSE 8080 8081 9990

CMD ["/home/bedework/run.sh"]
