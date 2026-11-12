## This file was originally made to fascilitate support for both python2 and python3.


class WireBytes(bytes):
    """Bytes that are sent exactly as they are: ``to_wire()`` leaves
    them alone instead of normalising their line endings to CRLF.  Used
    by ``save(raw_data=...)``."""


def to_wire(text):
    if text is None:
        return None
    if isinstance(text, WireBytes):
        return text
    if isinstance(text, str):
        text = bytes(text, "utf-8")
    text = text.replace(b"\n", b"\r\n")
    text = text.replace(b"\r\r\n", b"\r\n")
    return text


def to_local(text):
    if text is None:
        return None
    if not isinstance(text, str):
        text = text.decode("utf-8")
    text = text.replace("\r\n", "\n")
    return text


to_str = to_local


def to_normal_str(text):
    """
    Make sure we return a normal string
    """
    if text is None:
        return text
    if not isinstance(text, str):
        text = text.decode("utf-8")
    text = text.replace("\r\n", "\n")
    return text


def to_unicode(text):
    if text and isinstance(text, bytes):
        return text.decode("utf-8")
    return text


def entity_tag(text: str | None) -> str | None:
    """An ETag as an entity-tag (RFC 9110 section 8.8.3), quoted where a
    server left the quotes out: Ox in a multistatus getetag, Robur in an
    ETag header, though a GET of the object answers with them.  Whitespace
    around it, as pretty-printed XML has, is not part of the tag, and an
    empty one is no tag at all."""
    if not text or not text.strip():
        return None
    tag = text.strip()
    if tag.startswith(('"', 'W/"')):
        return tag
    if tag.startswith("W/"):
        return f'W/"{tag[2:]}"'
    return f'"{tag}"'
