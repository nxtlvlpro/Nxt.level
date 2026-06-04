"""Add new i18n keys (cookies.* + legal.*) to translations.js for all 10 langs.
EN + RU written manually; the other 8 use DeepSeek batch translation."""
import asyncio
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

PATH = Path("/app/frontend/src/i18n/translations.js")

# Source of truth — EN strings. Other languages derived from these.
EN_NEW = {
    "cookies.body": "We use functional storage to keep the app running (language preference, chat session). No tracking, no marketing.",
    "cookies.policy_link": "Privacy Policy",
    "cookies.accept": "Accept",
    "cookies.necessary": "Necessary only",

    "legal.back": "Back",
    "legal.last_updated": "Last updated",

    "legal.privacy.title": "Privacy Policy",
    "legal.privacy.p1": "NXT8 operates a B2B AI platform. We collect only the data strictly required to deliver the service: account credentials, chat history with our agents, uploaded documents you choose to send for analysis, and basic operational telemetry.",
    "legal.privacy.p2": "We do not sell personal data. We do not use third-party advertising trackers. Payments are processed by Stripe and never touch our servers; card data never reaches NXT8.",
    "legal.privacy.p3": "You may request a full export or deletion of your data at any time by writing to privacy@nxt8.pro. We respond within 30 days as required by GDPR, the UK DPA, and Russian Federal Law 152-FZ.",
    "legal.privacy.p4": "When you upload a document or photo to the chat, it is processed by our compliance and vision pipelines (OpenAI / DeepSeek). The file is stored on our infrastructure and is not used to train external models.",
    "legal.privacy.p5": "Functional storage (browser localStorage) holds your language preference and chat session id only. Clearing browser storage revokes this immediately.",

    "legal.terms.title": "Terms of Service",
    "legal.terms.p1": "By using NXT8 you agree to lawful, professional use of the platform. You are responsible for the content you upload and the actions you authorise our agents to take on your behalf.",
    "legal.terms.p2": "NXT8 is provided “as is” for the duration of your subscription. We commit to industry-standard uptime and security; we do not warrant fitness for any specific business outcome.",
    "legal.terms.p3": "Subscriptions are billed monthly via Stripe. You may cancel at any time; access remains until the end of the billing period already paid.",
    "legal.terms.p4": "Any disputes will be governed by the laws of the contracting entity, applied in good faith. For test-mode access (Pilot plan) no payment is taken and no contract is created.",
}

RU_NEW = {
    "cookies.body": "Мы используем функциональное хранилище для работы сервиса (выбор языка, сессия чата). Никакого трекинга, никакого маркетинга.",
    "cookies.policy_link": "Политика конфиденциальности",
    "cookies.accept": "Принять",
    "cookies.necessary": "Только необходимые",

    "legal.back": "Назад",
    "legal.last_updated": "Обновлено",

    "legal.privacy.title": "Политика конфиденциальности",
    "legal.privacy.p1": "NXT8 — это B2B-платформа ИИ. Мы собираем только данные, строго необходимые для работы сервиса: учётные данные, историю общения с агентами, загруженные вами на анализ документы и базовую операционную телеметрию.",
    "legal.privacy.p2": "Мы не продаём персональные данные. Мы не используем сторонние рекламные трекеры. Платежи обрабатывает Stripe и они не проходят через наши серверы; данные карт никогда не попадают в NXT8.",
    "legal.privacy.p3": "Вы можете запросить полный экспорт или удаление ваших данных, написав на privacy@nxt8.pro. Мы отвечаем в течение 30 дней — в соответствии с GDPR, UK DPA и 152-ФЗ.",
    "legal.privacy.p4": "Когда вы загружаете документ или фото в чат, файл обрабатывается нашими compliance- и vision-пайплайнами (OpenAI / DeepSeek). Файл хранится на нашей инфраструктуре и не используется для обучения внешних моделей.",
    "legal.privacy.p5": "Функциональное хранилище браузера (localStorage) содержит только ваш выбор языка и идентификатор сессии чата. Очистка хранилища браузера немедленно аннулирует эти данные.",

    "legal.terms.title": "Условия использования",
    "legal.terms.p1": "Используя NXT8, вы соглашаетесь применять платформу законно и профессионально. Вы несёте ответственность за загруженный контент и за действия, которые поручаете выполнять нашим агентам от вашего имени.",
    "legal.terms.p2": "NXT8 предоставляется «как есть» в течение оплаченного периода подписки. Мы гарантируем индустриальные стандарты доступности и безопасности; мы не гарантируем достижение конкретного бизнес-результата.",
    "legal.terms.p3": "Подписки оплачиваются ежемесячно через Stripe. Вы можете отменить подписку в любой момент; доступ сохраняется до конца уже оплаченного периода.",
    "legal.terms.p4": "Споры разрешаются по законам страны заключения договора в духе добросовестности. Для тестового режима (тариф Pilot) оплата не взимается и договор не заключается.",
}

OTHER_LANGS = {
    "es": "Spanish (Spain)",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese (Brazil)",
    "it": "Italian",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "tr": "Turkish",
}


async def translate(target_code: str, target_name: str) -> dict:
    import sys
    sys.path.insert(0, "/app/backend")
    from core.deepseek import get_deepseek
    ds = get_deepseek()
    prompt = (
        f"You are translating legal & UI strings for NXT8, a B2B AI platform. "
        f"Target language: {target_name}.\n"
        "Rules:\n"
        "1. Return ONLY JSON mapping the SAME keys to translations.\n"
        "2. Keep these tokens verbatim: NXT8, Stripe, OpenAI, DeepSeek, GDPR, UK DPA, "
        "152-ФЗ → translate to the local term if widely used, otherwise keep as-is.\n"
        "3. Preserve email addresses (privacy@nxt8.pro) verbatim.\n"
        "4. Match the legal/professional tone of the source.\n"
        "5. No markdown fences."
    )
    resp = await ds.chat(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(EN_NEW, ensure_ascii=False)},
        ],
        temperature=0.2, max_tokens=3000, request_logprobs=False,
    )
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (resp.get("content") or "").strip(),
                 flags=re.IGNORECASE)
    return json.loads(raw)


async def main():
    new_by_lang = {"en": EN_NEW, "ru": RU_NEW}
    for code, name in OTHER_LANGS.items():
        print(f"\n=== {code} ===")
        new_by_lang[code] = await translate(code, name)
        print(f"  {len(new_by_lang[code])} keys")

    src = PATH.read_text()
    for code in ["en", "ru", "es", "fr", "de", "pt", "it", "zh", "ja", "tr"]:
        new_kv = new_by_lang[code]
        new_lines = "".join(
            f'    "{k}": {json.dumps(v, ensure_ascii=False)},\n' for k, v in new_kv.items()
        )
        # Inject right before the closing  '\n  },' of this language block.
        block_re = re.compile(rf'(  {code}:\s*\{{)(.*?)(\n  \}},)', re.DOTALL)
        m = block_re.search(src)
        if not m:
            print(f"!! {code} block not found")
            continue
        body = m.group(2)
        # Skip if already injected
        if '"cookies.body"' in body and '"legal.privacy.title"' in body:
            print(f"   {code}: already has new keys, skip")
            continue
        new_body = body.rstrip() + "\n" + new_lines.rstrip("\n") + "\n  "
        src = src[:m.start(2)] + "\n" + new_body + src[m.end(2):]
        print(f"OK {code}: injected {len(new_kv)} new keys")
    PATH.write_text(src)
    print(f"\nWrote {len(src)} bytes")


if __name__ == "__main__":
    asyncio.run(main())
