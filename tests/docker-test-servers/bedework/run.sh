#!/bin/bash
# Container entrypoint: bring up the four processes a Bedework demo needs
# (apacheds, h2, opensearch, wildfly) and stay attached to wildfly.
#
# bwstartall.sh does the same thing, but it gives us no way to wait for
# opensearch before wildfly starts indexing, and it backgrounds wildfly.

set -e

export JAVA_HOME="${JAVA_HOME:-/opt/java/openjdk}"
cd "$JBOSS_HOME"

echo "=== starting apacheds ==="
./bin/bwdirstart.sh

echo "=== waiting for apacheds ==="
for i in $(seq 1 60); do
    if (echo > /dev/tcp/127.0.0.1/10389) 2>/dev/null; then
        echo "apacheds is up"
        break
    fi
    [ "$i" -eq 60 ] && { echo "apacheds did not come up" >&2; exit 1; }
    sleep 2
done

echo "=== starting h2 ==="
./bin/bwstarth2.sh

echo "=== starting opensearch ==="
./bin/bwstartoschqs.sh

echo "=== waiting for opensearch ==="
for i in $(seq 1 60); do
    if curl -sf http://localhost:9200/_cluster/health >/dev/null; then
        echo "opensearch is up"
        break
    fi
    [ "$i" -eq 60 ] && { echo "opensearch did not come up" >&2; exit 1; }
    sleep 5
done

echo "=== starting wildfly ==="
exec ./bin/bwstartwildfly.sh
