
#!/usr/bin/env python
# -*- encoding: utf-8 -*-

try:
    from .conf_private import caldav_servers
except ImportError:
    caldav_servers = []

# caldav_servers.append({"url": "http://sogo1:sogo1@sogo-demo.inverse.ca:80/SOGo/dav/", "principal_url": "http://sogo-demo.inverse.ca:80/SOGo/dav/sogo1/", "backwards_compatibility_url": "http://sogo1:sogo1@sogo-demo.inverse.ca:80/SOGo/dav/sogo1/Calendar/"})
# caldav_servers.append({"url": "https://sogo1:sogo1@sogo-demo.inverse.ca:443/SOGo/dav/sogo1/Calendar/"})
caldav_servers.append({"url": "http://baikal.tobixen.no:80/cal.php/", "username": "testlogin", "password": "testing123", "principal_url": "http://baikal.tobixen.no:80/cal.php/principals/testlogin/", "backwards_compatibility_url": "http://testlogin:testing123@baikal.tobixen.no:80/cal.php/calendars/testlogin/"})
#caldav_servers.append({"url": "http://veryveryveeeeerylongusernametest:thispasswordismaybenotlongenoughbutmaybemaybemaybeitislongenoughafterallhowlongdoesatoolongpasswordneedtobeiwonder@baikal.tobixen.no/cal.php"})

proxy = "127.0.0.1:8080"
proxy_noport = "127.0.0.1"
