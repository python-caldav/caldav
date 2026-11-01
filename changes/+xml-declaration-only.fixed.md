A response holding only an XML declaration, as Zimbra gives to a calendar-multiget naming an href without `.ics`, raised lxml's `XMLSyntaxError`.  It is now taken as a response without content.
