from six import PY3
from six import string_types


def isPython3():
    """Deprecated. Use six.PY3"""
    return PY3


def to_wire(text):
    if text is None:
        return None
    if isinstance(text, string_types) and PY3:
        text = bytes(text, "utf-8")
    elif not PY3:
        text = to_unicode(text).encode("utf-8")
    text = text.replace(b"\n", b"\r\n")
    text = text.replace(b"\r\r\n", b"\r\n")
    return text


def to_local(text):
    if text is None:
        return None
    if not isinstance(text, string_types):
        text = text.decode("utf-8")
    text = text.replace("\r\n", "\n")
    return text


to_str = to_local


def to_normal_str(text):
    """
    A str object is a unicode on python3 and a byte string on python2.
    Make sure we return a normal string, no matter what version of
    python ...
    """
    if text is None:
        return text
    if PY3 and not isinstance(text, str):
        text = text.decode("utf-8")
    elif not PY3 and not isinstance(text, str):
        text = text.encode("utf-8")
    text = text.replace("\r\n", "\n")
    return text


def to_unicode(text):
    if (
        text
        and isinstance(text, string_types)
        and not PY3
        and not isinstance(text, unicode)
    ):
        return unicode(text, "utf-8")
    if PY3 and text and isinstance(text, bytes):
        return text.decode("utf-8")
    return text
