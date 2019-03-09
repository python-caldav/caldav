#!/usr/bin/env python
# -*- encoding: utf-8 -*-

############################
# Private test server config
############################
try:
    from .conf_private import caldav_servers
except ImportError:
    caldav_servers = []

try:
    from .conf_private import only_private
except ImportError:
    only_private = False

#####################
# Public test servers
#####################
if not only_private:
    
    ## TODO: this one is set up on emphemeral storage on OpenShift and
    ## then configured manually through the webui installer, it will
    ## most likely only work for some few days until it's down again.
    ## It's needed to hard-code the configuration into
    ## https://github.com/python-caldav/baikal
    
    caldav_servers.append({
        "url": "http://baikal-caldav-servers.cloudapps.bitbit.net/html/cal.php/",
        "username": "baikaluser",
        "password": "asdf"})

    # radicale - too many problems, postponing
    # caldav_servers.append({
    #     "url": "http://radicale.caldav-servers.tobixen.no/testuser/",
    #     "username": "testuser",
    #     "password": "123"})

    # bedework:
    # * todos and journals are not properly supported -
    #   ref https://github.com/Bedework/bedework/issues/5
    # * propfind fails to return resourcetype,
    #   ref https://github.com/Bedework/bedework/issues/110
    # * date search on recurrences of recurring events doesn't work
    #   (not reported yet - TODO)
    caldav_servers.append({
        "url": "http://bedework-caldav-servers.cloudapps.bitbit.net/ucaldav/",
        "username": "vbede",
        "password": "bedework",
        "nojournal": True,
        "notodo": True,
        "nopropfind": True,
        "norecurring": True})

    caldav_servers.append({
        "url": "http://xandikos-caldav-servers.cloudapps.bitbit.net/",
        "username": "user1",
        "password": "password1"
        })

proxy = "127.0.0.1:8080"
proxy_noport = "127.0.0.1"
