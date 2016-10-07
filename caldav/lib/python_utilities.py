import sys
from six import string_types


def isPython3():
    return sys.version_info >= (3, 0)


def to_wire(text):
    if text and isinstance(text, string_types) and isPython3():
        text = bytes(text, 'utf-8')
    elif not isPython3():
        text = to_unicode(text).encode('utf-8')
    return text


def to_local(text):
    if text and not isinstance(text, string_types):
        text = text.decode('utf-8')
    return text


def to_str(text):
    if text and not isinstance(text, string_types):
        text = text.decode('utf-8')
    return text


def to_unicode(text):
    if text and isinstance(text, string_types) and not isPython3() and not isinstance(text, unicode):
        text = unicode(text, 'utf-8')
    return text
