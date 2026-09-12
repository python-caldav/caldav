# Sourced by wildfly/apacheds/bin/apacheds.sh (its documented hook for local
# customisation).  Installed by the Dockerfile.
#
# The ApacheDS bundled with the feature pack does not run on JDK 21, even
# though that is the JDK upstream tells you to install.  On startup it builds a
# temporary self-signed certificate through sun.security.x509, which needs
# both an --add-exports to reach at all and a method - X509CertInfo.set(String,
# Object) - that JDK 18 removed.  So run just this one process on a JRE 17 that
# the image carries alongside the JDK 21 everything else uses.

JAVA_HOME=/opt/java/jdk17
JAVA_OPTS="$JAVA_OPTS --add-exports java.base/sun.security.x509=ALL-UNNAMED"
JAVA_OPTS="$JAVA_OPTS --add-exports java.base/sun.security.util=ALL-UNNAMED"
