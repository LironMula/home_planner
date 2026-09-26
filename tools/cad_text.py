"""Recover the legacy Hebrew SHX byte encoding used by this architect's DXF."""

import re


def decode_architect_text(value):
    """Return logical Hebrew while retaining the order within numeric runs.

    This drawing stores visual-order DOS Hebrew bytes interpreted as CP1252.
    Only apply the conversion if it recovers Hebrew; retain other encodings.
    """
    if any("\u0590" <= char <= "\u05ff" for char in value):
        return value
    try:
        decoded = value.encode("cp1252", errors="surrogateescape").decode("cp862")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    if not any("\u05d0" <= char <= "\u05ea" for char in decoded):
        return value
    logical = decoded[::-1]
    return re.sub(r"[0-9]+(?:[.,][0-9]+)*", lambda match: match.group()[::-1], logical)
