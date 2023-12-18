from lxml import etree


def xmlstring(root):
    if hasattr(root, "xmlelement"):
        root = root.xmlelement()
    return etree.tostring(root, pretty_print=True).decode("utf-8")


def printxml(root) -> None:
    print(xmlstring(root))
