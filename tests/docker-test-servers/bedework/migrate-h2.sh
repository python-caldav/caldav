#!/bin/bash
# Convert the quickstart H2 databases to the format the shipped driver reads.
#
# The 5.0.0 feature pack pre-seeds its demo databases from bw-quickstart, which
# last released in 2022 and wrote them with H2 1.4.x (MVStore "format:1").  The
# same feature pack installs the H2 2.2.224 driver, which refuses to open them:
#
#   The write format 1 is smaller than the supported format 3 [2.2.224/5]
#
# So dump each database with a contemporary H2 and reload it with the driver
# the server actually uses.  The dumps need exactly one fixup: H2 1.4.x writes
# unbounded columns as VARCHAR(2147483647), above H2 2.x's precision limit.
#
# Runs at image build time; see Dockerfile.

set -eu

H2_LEGACY_VERSION="${1:?usage: migrate-h2.sh <legacy-h2-version>}"

h2new=$(ls /home/bedework/wildfly/modules/system/layers/base/com/h2database/h2/main/h2-*.jar)
h2old=/tmp/h2-legacy.jar
work=/tmp/h2mig

curl -sSLo "$h2old" \
    "https://repo1.maven.org/maven2/com/h2database/h2/${H2_LEGACY_VERSION}/h2-${H2_LEGACY_VERSION}.jar"

mkdir -p "$work"
cd /home/bedework/wildfly/standalone/data/bedework/h2

for f in *.mv.db; do
    db="${f%.mv.db}"
    echo "migrating $db"
    java -cp "$h2old" org.h2.tools.Script \
        -url "jdbc:h2:$PWD/$db" -user sa -password sa -script "$work/$db.sql"
    sed -i 's/VARCHAR(2147483647)/VARCHAR(1000000000)/g' "$work/$db.sql"
    rm -f "$db.mv.db" "$db.trace.db"
    java -cp "$h2new" org.h2.tools.RunScript \
        -url "jdbc:h2:$PWD/$db" -user sa -password sa -script "$work/$db.sql"
done

rm -f ./*.trace.db
rm -rf "$work" "$h2old"
