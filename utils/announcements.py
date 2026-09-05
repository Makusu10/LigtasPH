"""Announcement display helpers (display-only — stored rows are untouched)."""


def dedup_message(title, message):
    """Strip a title echo from the start of a message.

    Admins often paste "<title> <body>" into the message field, so banners
    and tables read the title twice. If the message opens with the title
    (case-insensitive, ignoring leading quotes/whitespace), that prefix plus
    any trailing separator (":", "-", quotes, spaces) is removed. Never
    returns an empty string: if nothing would remain, the original stands.
    """
    t = (title or "").strip()
    m = (message or "").strip()
    if not t or not m or len(m) <= len(t):
        return message
    lead = m[: len(t) + 8].lstrip(" \t\"'“”‘’«»")
    if lead[: len(t)].lower() != t.lower():
        return message
    # Cut using the unstripped length so inner spacing survives.
    cut = m.lstrip(" \t\"'“”‘’«»")
    rest = cut[len(t):].lstrip(" \t\"'“”‘’«»:;,.—–-")
    return rest if rest else message
