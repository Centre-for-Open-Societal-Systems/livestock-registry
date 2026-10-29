"""Nothing staff read in the Livestock registry is a code.

Reads the metadata the registry is built from (no database): the section JSON
that defines every form and table, the English translations, and the overlay
that rewrites code labels. A label, option, placeholder, title or message that
still shows an underscore or an ALL CAPS code fails here, as does a
validation message in the extension that names a field by its key.
"""
import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "livestock-extension/src/openg2p_registry_livestock_extension"
META = PACKAGE / "meta_data"
OVERLAY = META / "zz-oan/85_readable_text.sql"

# Known short forms (DOVAR and LITS are source systems) and the date format
# mask are allowed to stay in capitals.
ALLOWED = {"ID", "FAN", "FIN", "GPS", "DA", "ODK", "AI", "DD/MM/YYYY", "ET", "DOVAR", "LITS"}
TEXT_KEYS = {
    "widget-label", "label", "display_label", "widget-data-placeholder", "widget-placeholder",
    "section-title", "widget-data-dialog-title-add", "widget-data-dialog-title-edit",
    "patternMessage", "notBeforeFieldMessage", "minDateMessage",
}


def literals(text):
    """The single-quoted SQL string literals of a script, comments skipped."""
    i, n = 0, len(text)
    while i < n:
        if text[i] == "'":
            j, buf = i + 1, []
            while j < n:
                if text[j] == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    break
                buf.append(text[j])
                j += 1
            yield "".join(buf)
            i = j + 1
        elif text[i:i + 2] == "--":
            while i < n and text[i] != "\n":
                i += 1
        else:
            i += 1


def json_in(path):
    for literal in literals(path.read_text(encoding="utf-8")):
        if literal.strip()[:1] in "{[":
            try:
                yield json.loads(literal)
            except ValueError:
                continue


def translations():
    """English translations as the replay leaves them: the seed row, then every
    overlay that merges named keys, in file order."""
    merged = {}
    seed = list(literals((META / "registry-configurations/registry_languages.sql").read_text(encoding="utf-8")))
    for literal in seed:
        if literal.startswith('{"'):
            merged.update(json.loads(literal))
    for path in sorted(META.rglob("*.sql")):
        if path.name == "registry_languages.sql":
            continue
        body = path.read_text(encoding="utf-8")
        if "registry_languages" not in body:
            continue
        for literal in literals(body):
            if literal.startswith("{") and '":' in literal:
                try:
                    parsed = json.loads(literal)
                except ValueError:
                    continue
                if parsed and all(isinstance(v, str) for v in parsed.values()):
                    merged.update(parsed)
    return merged


def overlay_maps():
    body = OVERLAY.read_text(encoding="utf-8")
    maps = [json.loads(m) for m in re.findall(r":= '(\{.*?\})';", body, re.S)]
    labels, placeholders = maps
    return labels, placeholders


def visible_texts():
    labels, placeholders = overlay_maps()
    shown = translations()
    found = []

    def walk(node, where):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and key in TEXT_KEYS:
                    text = placeholders.get(value) or (labels.get(value) if key == "label" else None) or value
                    found.append((where, key, shown.get(text, text)))
                else:
                    walk(value, where)
        elif isinstance(node, list):
            for value in node:
                walk(value, where)

    for path in sorted(META.rglob("*.sql")):
        if path.name in ("registry_languages.sql", "85_readable_text.sql"):
            continue
        for parsed in json_in(path):
            walk(parsed, path.name)
    return found


def looks_like_code(text):
    words = re.findall(r"[A-Za-z0-9/]+", text)
    if "_" in text:
        return True
    return bool(re.fullmatch(r"[A-Z][A-Z0-9 /&-]{2,}", text)) and text not in ALLOWED and not all(w in ALLOWED for w in words)


def message_text(node):
    """The literal words of a message expression; values looked up inside it
    (record.get("some_key")) are not words."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for value in node.values:
            yield from message_text(value)
    elif isinstance(node, ast.BinOp):
        yield from message_text(node.left)
        yield from message_text(node.right)


class ReadableTextTests(unittest.TestCase):
    def test_no_label_option_placeholder_or_message_is_a_code(self):
        bad = sorted({(where, key, text) for where, key, text in visible_texts()
                      if looks_like_code(text) and not text.startswith("coss_")})
        self.assertEqual([], bad)

    def test_translated_messages_have_no_keys(self):
        bad = {k: v for k, v in translations().items()
               if k.startswith(("coss_", "ls_")) and isinstance(v, str) and looks_like_code(v)}
        self.assertEqual({}, bad)

    def test_overlay_runs_after_the_other_text_overlays(self):
        files = sorted(str(p.relative_to(META)).replace("\\", "/") for p in META.rglob("*.sql"))
        mine = files.index("zz-oan/85_readable_text.sql")
        for earlier in ("zz-oan/30_label_casing.sql", "zz-oan/40_farmer_tab_layout.sql"):
            self.assertLess(files.index(earlier), mine)

    def test_overlay_keeps_option_values(self):
        body = OVERLAY.read_text(encoding="utf-8")
        self.assertNotIn("'{value}'", body)
        self.assertIn("jsonb_set(result, '{label}'", body)
        self.assertNotIn("NOT IN", body)

    def test_validation_messages_do_not_name_fields_by_key(self):
        offenders = []
        for path in sorted(PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                if name not in ("validation_error", "_invalid"):
                    continue
                for part in message_text(node.args[0] if node.args else node):
                    for word in re.findall(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+", part):
                        offenders.append(f"{path.name}:{node.lineno}: {word}")
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
