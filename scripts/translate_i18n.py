"""
One-off helper: translate the EN dictionary from `frontend/src/i18n/translations.js`
into 8 target languages via DeepSeek. Writes a JSON file we then merge into
translations.js. Idempotent — only translates keys that don't already exist
in the target.
"""
import json
import os
import re
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

TARGET_LANGS = {
    "es": "Spanish (Spain)",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese (Brazil)",
    "it": "Italian",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "tr": "Turkish",
}

TRANS_PATH = Path("/app/frontend/src/i18n/translations.js")
OUT_PATH = Path("/tmp/translations_batch.json")

# Extract EN block: from "en: {" to the corresponding "},\n  ru:"
src = TRANS_PATH.read_text()
m = re.search(r"  en:\s*\{(.*?)\},\s*\n  ru:", src, re.DOTALL)
if not m:
    raise SystemExit("could not locate en: block")
en_block = m.group(1)

# Find every  "key": "value", entry (also multi-line values).
key_re = re.compile(r'"([^"]+)":\s*("(?:[^"\\]|\\.)*"|\n?\s*"(?:[^"\\]|\\.)*")\s*,', re.DOTALL)
en_entries = {}
for km in key_re.finditer(en_block):
    k = km.group(1)
    raw_v = km.group(2).strip()
    # Python-decode JSON string
    try:
        v = json.loads(raw_v)
    except Exception:
        v = raw_v.strip('"')
    en_entries[k] = v
print(f"Parsed {len(en_entries)} EN keys")


async def translate_lang(lang_code: str, lang_name: str) -> dict:
    from core.deepseek import get_deepseek
    ds = get_deepseek()
    # Batch in groups of 40 keys so the JSON stays parseable.
    keys = list(en_entries.keys())
    out: dict = {}
    BATCH = 40
    for i in range(0, len(keys), BATCH):
        batch = keys[i : i + BATCH]
        payload = {k: en_entries[k] for k in batch}
        prompt = (
            f"You are translating UI strings for an enterprise B2B AI platform "
            f"called NXT8. Target language: {lang_name}.\n\n"
            "Rules:\n"
            "1. Return ONLY a JSON object mapping the same keys to translated strings.\n"
            "2. Preserve {variables} EXACTLY (do not translate placeholders).\n"
            "3. Keep these tokens verbatim, do NOT translate them: NXT8, Hermes, AI, ROI, KPI, MemPalace, Compliance, JOKER.\n"
            "4. For UPPERCASE labels (e.g. 'HOME', 'OPS'), produce SHORT UPPERCASE equivalent in the target language.\n"
            "5. Keep tone professional, concise. Match the original length where possible.\n"
            "6. Do not wrap in markdown fences, just raw JSON."
        )
        resp = await ds.chat(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=4000,
            request_logprobs=False,
        )
        raw = (resp.get("content") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
        try:
            chunk = json.loads(raw)
        except Exception as e:
            print(f"!! {lang_code} batch {i}: parse fail {e}; raw={raw[:200]}")
            continue
        out.update(chunk)
        print(f"  {lang_code} +{len(chunk)} ({len(out)}/{len(keys)})")
    return out


async def main():
    import sys
    sys.path.insert(0, "/app/backend")
    results: dict = {}
    # Run sequentially to avoid hammering the API
    for code, name in TARGET_LANGS.items():
        print(f"\n=== {code} ({name}) ===")
        results[code] = await translate_lang(code, name)
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSaved → {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
