from lxml import etree


def xmlstring(root):
    return etree.tostring(root.xmlelement(), pretty_print=True).decode("utf-8")


def printxml(root):
    print(xmlstring(root))
