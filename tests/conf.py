#!/usr/bin/env python
# -*- encoding: utf-8 -*-

try:
    from conf_private import caldav_servers
except:
    caldav_servers = []

caldav_servers.append({"url": "http://sogo1:sogo1@sogo-demo.inverse.ca:80/SOGo/dav/sogo1/Calendar/"})
caldav_servers.append({"url": "http://sogo-demo.inverse.ca:80/SOGo/dav/sogo1/Calendar/", "username": "sogo1", "password": "sogo1"})
## This one is not available anymore
#caldav_servers.append({"url": "https://sogo1:sogo1@sogo-demo.inverse.ca:443/SOGo/dav/sogo1/Calendar/"})
## This one is either very broken, or this caldav library is very incompatible with baikal
#caldav_servers.append({"url": "http://testlogin:testing123@baikal.tobixen.no:80/cal.php/")

proxy = "127.0.0.1:8080"
proxy_noport = "127.0.0.1"
