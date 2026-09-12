#!/bin/bash
# Work around an upstream packaging bug in bw-wf-feature-pack 5.0.0.
#
# CalSvcFactoryDefault lives in the shared module org.bedework.calendar.
# common.api.rw and loads org.bedework.dumprestore.BwDumpRestore reflectively
# through the thread context classloader - i.e. through whichever war is
# serving the request.  The dumprestore module is only listed as a dependency
# of org.bedework.calendar.rw-war, so a request to a war built on the
# read-only module (bw-webclient-cal, at /cal) throws ClassNotFoundException.
#
# That would just break /cal, except the failure is a static initialiser in a
# *shared* module: once it has failed, every later caller - /ucaldav included -
# gets NoClassDefFoundError and 500s until wildfly is restarted.  Whichever
# request lands first decides whether the server works at all.
#
# So add the dependency to the read-only module too.
#
# Runs at image build time; see Dockerfile.

set -eu

modules=/home/bedework/wildfly/modules/system/layers/base/org/bedework/calendar
ro_war="$modules/ro-war/main/module.xml"

grep -q 'name="org.bedework.calendar.dumprestore"' "$ro_war" && exit 0

sed -i 's|<dependencies>|<dependencies>\n        <module export="true" name="org.bedework.calendar.dumprestore"/>|' \
    "$ro_war"

grep -q 'name="org.bedework.calendar.dumprestore"' "$ro_war"
echo "added dumprestore dependency to org.bedework.calendar.ro-war"
