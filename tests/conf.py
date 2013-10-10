#!/usr/bin/env python
# -*- encoding: utf-8 -*-

try:
    from conf_private import caldav_urls
except:
    caldav_urls = []

caldav_urls.append("http://sogo1:sogo1@sogo-demo.inverse.ca:80/SOGo/dav/sogo1/Calendar/")
caldav_urls.append("https://sogo1:sogo1@sogo-demo.inverse.ca:443/SOGo/dav/sogo1/Calendar/")
caldav_urls.append("http://testlogin:testing123@baikal.tobixen.no:80/cal.php/")

proxy = "127.0.0.1:8080"
proxy_noport = "127.0.0.1"
