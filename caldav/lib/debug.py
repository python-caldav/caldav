def xml(root):
    return etree.tostring(x.xmlelement(), pretty_print=True).decode("utf-8")


def printxml(root):
    print(xml(root))
