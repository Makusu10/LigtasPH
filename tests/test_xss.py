"""GH issue #6: client-side output encoding.

Static layer (always runs): every public template defines esc() with
single-quote coverage, and no server-data interpolation reaches innerHTML
unescaped. Behavioral layer (needs node): the shipped esc() from map.html
is executed against adversarial payloads, including the issue's
'a\\" <>'b cluster-popup drill.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "public"

_ESC_FILES = ["map.html", "weather.html", "home.html", "directory.html", "hotlines.html"]

# (file, raw patterns that must NOT appear outside esc(...))
_RAW_SINKS = [
    ("directory.html", [r"\$\{c\.name\}", r"\$\{c\.address\}", r"\$\{c\.city\}",
                        r"\$\{c\.occupancy_status\}", r"\$\{c\.food_status\}",
                        r"\$\{c\.water_status\}", r"\$\{c\.basic_needs_status\}",
                        r"\$\{c\.updated_at\}", r"\$\{c\.facility_type\}",
                        r"\$\{c\.site_kind\}"]),
    ("hotlines.html", [r"\$\{h\.agency\}", r"\$\{h\.category\}", r"\$\{h\.city\}",
                       r"\$\{h\.address_area\}", r"\$\{h\.contact_number\}",
                       r"\$\{h\.last_verified", r"\$\{h\.verification_note"]),
    ("weather.html", [r"\$\{e\.message\}", r"\$\{env\.errors", r"\$\{h\.desc\|"]),
    ("home.html", [r"Weather — \$\{wlabel\}", r"\$\{d\.weather",
                   r"\$\{d\.source", r"\$\{d\.fetched_at"]),
]


def _src(name):
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def test_esc_covers_single_quote_everywhere():
    for name in _ESC_FILES:
        src = _src(name)
        assert "&#39;" in src, f"{name} esc() must escape single quotes"


@pytest.mark.parametrize("name,patterns", _RAW_SINKS)
def test_no_raw_server_interpolation(name, patterns):
    src = _src(name)
    for pat in patterns:
        for m in re.finditer(pat, src):
            after = src[m.end():m.end() + 1]
            if after == "?":
                continue  # ternary truthiness check, not HTML output
            # the match must sit inside an esc(...) call: look back for 'esc('
            # with no closing paren in between (allows nested calls/args)
            before = src[max(0, m.start() - 60):m.start()]
            assert re.search(r"esc\([^()]*$", before), \
                f"{name}: raw interpolation near {m.group(0)!r}"


def _extract_esc(src):
    m = re.search(r"function esc\(s\)\{[^}]*\}", src)
    assert m, "esc() definition not found"
    return m.group(0)


@pytest.mark.skipif(shutil.which("node") is None, reason="node required for JS drill")
def test_shipped_esc_neutralizes_adversarial_names():
    esc_js = _extract_esc(_src("map.html"))
    payloads = [
        "'a\"<>'b",  # the issue's cluster-popup drill
        "<img src=x onerror=alert(1)>",
        "' onmouseover='alert(1)",
        "\"><script>alert(1)</script>",
        "&lt;already-escaped&gt;",
    ]
    harness = (
        esc_js + "\n"
        "const out = PAYLOADS.map(esc);\n"
        "console.log(JSON.stringify(out));"
    )
    probe = harness.replace(
        "PAYLOADS", repr(payloads)
    )
    r = subprocess.run(["node", "-e", probe], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    import json
    outs = json.loads(r.stdout)
    assert outs[0] == "&#39;a&quot;&lt;&gt;&#39;b"
    for raw, escaped in zip(payloads, outs):
        for ch in "<>\"'":
            if ch in raw:
                assert ch not in escaped, f"{ch!r} survived esc() in {raw!r}"
        # attribute-breakout drill: embedding must stay inside the quotes
        attr = f'data-name="{escaped}"'
        assert attr.count('"') == 2, f"breakout in {attr!r}"
