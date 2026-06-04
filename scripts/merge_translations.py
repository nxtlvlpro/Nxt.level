"""Merge /tmp/translations_batch.json into translations.js — insert each language
block right before SUPPORTED_LANGS export."""
import json
import re
from pathlib import Path

TRANS_PATH = Path("/app/frontend/src/i18n/translations.js")
BATCH = json.loads(Path("/tmp/translations_batch.json").read_text())

LANG_ORDER = ["es", "fr", "de", "pt", "it", "zh", "ja", "tr"]

src = TRANS_PATH.read_text()

# Build the new language blocks.
def fmt_block(code: str, entries: dict) -> str:
    lines = [f"  {code}: {{"]
    for k, v in entries.items():
        # JSON-quote both key and value.
        kj = json.dumps(k, ensure_ascii=False)
        vj = json.dumps(v, ensure_ascii=False)
        lines.append(f"    {kj}: {vj},")
    lines.append("  },")
    return "\n".join(lines)

new_blocks = "\n".join(fmt_block(code, BATCH[code]) for code in LANG_ORDER if code in BATCH)

# Locate end of ru block: find '\n  },\n};' after the ru: { ... }.
m = re.search(r"(  ru:\s*\{.*?\n  \},)\n(\};)", src, re.DOTALL)
if not m:
    raise SystemExit("could not locate end of ru block")

# Insert new blocks before the closing };
patched = src[:m.end(1)] + "\n" + new_blocks + "\n" + src[m.start(2):]

# Update SUPPORTED_LANGS
patched = re.sub(
    r'export const SUPPORTED_LANGS\s*=\s*\[[^\]]*\];',
    'export const SUPPORTED_LANGS = ["en", "ru", "es", "fr", "de", "pt", "it", "zh", "ja", "tr"];',
    patched,
)

TRANS_PATH.write_text(patched)
print(f"Wrote {len(patched)} bytes; final SUPPORTED_LANGS contains {len(LANG_ORDER)+2} languages.")
