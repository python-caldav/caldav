#!/bin/bash
set -e

OX_CONFIG_DATABASE_USER=${OX_CONFIG_DATABASE_USER:-"openxchange"}
OX_CONFIG_DATABASE_PASSWORD=${OX_CONFIG_DATABASE_PASSWORD:-"db_password"}

OX_ADMIN_MASTER_LOGIN=${OX_ADMIN_MASTER_LOGIN:-"oxadminmaster"}
OX_ADMIN_MASTER_PASSWORD=${OX_ADMIN_MASTER_PASSWORD:-"admin_master_password"}

OX_SERVER_NAME=${OX_SERVER_NAME:-"oxserver"}
OX_SERVER_MEMORY=${OX_SERVER_MEMORY:-"1024"}

OX_CONTEXT_ADMIN_LOGIN=${OX_CONTEXT_ADMIN_LOGIN:-"oxadmin"}
OX_CONTEXT_ADMIN_PASSWORD=${OX_CONTEXT_ADMIN_PASSWORD:-"oxadmin"}
OX_CONTEXT_ADMIN_EMAIL=${OX_CONTEXT_ADMIN_EMAIL:-"admin@example.com"}
OX_CONTEXT_ID=${OX_CONTEXT_ID:-"1"}

export PATH=$PATH:/opt/open-xchange/sbin/

echo "Starting MariaDB..."
# The /var/lib/mysql tmpfs mount starts empty (overlays the image layer).
# Set ownership and initialise system tables before starting the service.
chown -R mysql:mysql /var/lib/mysql
chmod 750 /var/lib/mysql
mariadb-install-db --user=mysql --datadir=/var/lib/mysql --skip-test-db 2>/dev/null
service mariadb start
sleep 5

echo "Configuring MariaDB root for TCP access (needed by initconfigdb)..."
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY ''; FLUSH PRIVILEGES;" || \
mysql -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD(''); FLUSH PRIVILEGES;" || \
mysql -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' IDENTIFIED BY '' WITH GRANT OPTION; FLUSH PRIVILEGES;"

echo "Initializing config database..."
/opt/open-xchange/sbin/initconfigdb \
    --configdb-user=${OX_CONFIG_DATABASE_USER} \
    --configdb-pass=${OX_CONFIG_DATABASE_PASSWORD} \
    --configdb-dbname=configdb \
    --configdb-host=localhost \
    --configdb-port=3306 \
    -a -i

echo "Running oxinstaller..."
/opt/open-xchange/sbin/oxinstaller \
    --no-license \
    --servername=${OX_SERVER_NAME} \
    --configdb-user=${OX_CONFIG_DATABASE_USER} \
    --configdb-pass=${OX_CONFIG_DATABASE_PASSWORD} \
    --configdb-readhost=localhost \
    --configdb-readport=3306 \
    --configdb-writehost=localhost \
    --configdb-writeport=3306 \
    --configdb-dbname=configdb \
    --master-pass=${OX_ADMIN_MASTER_PASSWORD} \
    --network-listener-host=localhost \
    --servermemory ${OX_SERVER_MEMORY}

# Pre-insert the server entry so OX can resolve its own server_id on startup.
# Without this, OX and registerserver form a circular dependency:
# OX needs the server entry to init its DB pool; registerserver needs OX running.
echo "Pre-registering server in configdb..."
NEXT_ID=$(mysql -u root configdb -sNe "SELECT id+1 FROM configdb_sequence;" 2>/dev/null)
mysql -u root configdb -e "
    INSERT IGNORE INTO server (server_id, name) VALUES (${NEXT_ID}, '${OX_SERVER_NAME}');
    UPDATE configdb_sequence SET id = ${NEXT_ID};
" 2>/dev/null

echo "Starting OX middleware (as open-xchange user)..."
mkdir -p /var/log/open-xchange
chown open-xchange:open-xchange /var/log/open-xchange
su -s /bin/bash open-xchange -c \
    "/opt/open-xchange/sbin/open-xchange >> /var/log/open-xchange/open-xchange-console.log 2>&1 &"

echo "Waiting for OX admin RMI service to be ready..."
max_attempts=60
for i in $(seq 1 $max_attempts); do
    if /opt/open-xchange/sbin/registerserver \
            --name=${OX_SERVER_NAME} \
            --adminuser=${OX_ADMIN_MASTER_LOGIN} \
            --adminpass=${OX_ADMIN_MASTER_PASSWORD} 2>/dev/null; then
        echo "Server registered via RMI."
        break
    fi
    # Also accept "already exists" as success
    ERR=$(/opt/open-xchange/sbin/registerserver \
            --name=${OX_SERVER_NAME} \
            --adminuser=${OX_ADMIN_MASTER_LOGIN} \
            --adminpass=${OX_ADMIN_MASTER_PASSWORD} 2>&1 || true)
    if echo "$ERR" | grep -qi "already\|exists\|duplicate"; then
        echo "Server already registered (OK)."
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "WARNING: registerserver did not succeed after ${max_attempts} attempts, continuing..."
        break
    fi
    echo -n "."
    sleep 5
done

echo ""
echo "Registering filestore..."
/opt/open-xchange/sbin/registerfilestore \
    --adminuser=${OX_ADMIN_MASTER_LOGIN} \
    --adminpass=${OX_ADMIN_MASTER_PASSWORD} \
    --storepath=file:/ox/store \
    --storesize=1000000

echo "Registering database..."
/opt/open-xchange/sbin/registerdatabase \
    --adminuser=${OX_ADMIN_MASTER_LOGIN} \
    --adminpass=${OX_ADMIN_MASTER_PASSWORD} \
    --name=oxdatabase \
    --hostname=localhost \
    --dbuser=${OX_CONFIG_DATABASE_USER} \
    --dbpasswd=${OX_CONFIG_DATABASE_PASSWORD} \
    --master=true

echo "Creating context..."
while ! /opt/open-xchange/sbin/createcontext \
    --adminuser=${OX_ADMIN_MASTER_LOGIN} \
    --adminpass=${OX_ADMIN_MASTER_PASSWORD} \
    --contextid=${OX_CONTEXT_ID} \
    --username=${OX_CONTEXT_ADMIN_LOGIN} \
    --password=${OX_CONTEXT_ADMIN_PASSWORD} \
    --email=${OX_CONTEXT_ADMIN_EMAIL} \
    --displayname="Context Admin" \
    --givenname=Admin \
    --surname=Admin \
    --addmapping=defaultcontext \
    --quota=1024 \
    --access-combination-name=groupware_standard
do
    echo "Retrying context creation..."
    sleep 5
done

echo "Starting Apache..."
service apache2 start || apache2ctl -t 2>&1 || true

echo "OX App Suite is ready."
tail -f /var/log/open-xchange/open-xchange-console.log 2>/dev/null || tail -f /dev/null
