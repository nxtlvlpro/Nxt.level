// NXT8 — UI translations. English is the default; Russian is opt-in via Burger menu.
// Keep keys flat-dotted for clarity. Use simple {var} placeholders.

export const TRANSLATIONS = {
  en: {
    // Burger menu
    "menu.title": "MENU",
    "menu.auth": "Sign in",
    "menu.lang": "Languages",
    "menu.about": "About",
    "menu.support": "Support",
    "menu.settings": "Settings",
    "menu.pricing": "Plans",
    "menu.back": "back",
    "menu.placeholder": "Placeholder · we'll wire this up later",
    "menu.auth.body": "Sign in & registration will live here.",
    "menu.lang.body": "Choose the interface language.",
    "menu.lang.current": "Current language",
    "menu.lang.note":
      "Affects all UI labels, the chat with Hermes and voice mode (STT + TTS).",
    "menu.lang.english": "English",
    "menu.lang.russian": "Russian",
    "menu.about.body": "About NXT8.PRO.",
    "menu.support.body": "Contact our support team.",
    "menu.settings.admin": "Admin sign-in",
    "menu.settings.admin.body": "4-digit PIN · we'll wire this up later",
    "menu.settings.client": "Screen & client settings",

    "pricing.individual": "Individual",
    "pricing.individual.desc": "For independent professionals and creators.",
    "pricing.individual.monthly": "$28 monthly",
    "pricing.individual.annual": "$20 annual",
    "pricing.team": "Team",
    "pricing.team.desc": "For companies and distributed teams.",
    "pricing.team.monthly": "from $18 per seat/month",
    "pricing.team.annual": "from $14 annual billing",

    // Seed error
    "seed.error": "backend unreachable — check the server",

    // Home — tickers
    "home.ticker.hero.1": "Welcome to NXT8",
    "home.ticker.hero.2": "AI coordination for modern teams",
    "home.ticker.hero.3": "Lives inside the tools you already use",
    "home.ticker.hero.4": "Less chaos · More coordination",
    "home.ticker.hero.5": "No heavy rollout",
    "home.ticker.features.documents": "Documents",
    "home.ticker.features.tasks": "Tasks",
    "home.ticker.features.calendar": "Calendar",
    "home.ticker.features.together": "It all works together",
    "home.ticker.pilot.1": "Onboard your first 10 teammates free",
    "home.ticker.pilot.2": "14-day diagnostic pilot",
    "home.ticker.pilot.3": "No long contracts",
    "home.ticker.pilot.4": "No commitments",

    // Home — intro card
    "home.intro.eyebrow": "operational ai system",
    "home.intro.title.before": "Operational AI system",
    "home.intro.title.accent": "for the modern business",
    "home.intro.body":
      "A ready-made AI team that works alongside your company. Less chaos. More coordination. No heavy rollout.",
    "home.intro.cta": "pick your AI agents",

    // Agents
    "home.agent.label": "agent",
    "home.agent.cta": "Connect",
    "home.agent.hermes.role": "Chief operations coordinator",
    "home.agent.hermes.plan": "Personal — $9 / employee",
    "home.agent.hermes.desc":
      "Coordinates tasks, captures decisions, helps the team keep context, and weaves company processes into a single system.",
    "home.agent.hr.role": "People growth",
    "home.agent.hr.plan": "Team — $14 / employee",
    "home.agent.hr.desc":
      "Helps every teammate grow. Spots burnout patterns, surfaces growth areas, and tailors development plans.",
    "home.agent.client.role": "Client manager",
    "home.agent.client.plan": "Team — $14 / employee",
    "home.agent.client.desc":
      "Handles client conversations, never loses a deal in the noise, drafts replies, and records commitments in the CRM.",
    "home.agent.analytics.role": "Team analyst",
    "home.agent.analytics.plan": "Headquarters — $24 / employee",
    "home.agent.analytics.desc":
      "Pulls data from every source and shows what is happening in the company right now. Plain answers instead of complex dashboards.",
    "home.agent.financial.role": "Financial helper",
    "home.agent.financial.plan": "Operations — $19 / employee",
    "home.agent.financial.desc":
      "Tracks money flow, reminds about payments, and helps plan the budget without spreadsheets or manual math.",
    "home.agent.legal.role": "Compliance with document review",
    "home.agent.legal.plan": "Operations — $19 / employee",
    "home.agent.legal.desc":
      "Reads contracts, policies and offers. Highlights risky clauses and suggests what to negotiate before signing.",
    "home.agent.marketing.role": "Marketing operator",
    "home.agent.marketing.plan": "Operations — $19 / employee",
    "home.agent.marketing.desc":
      "Tracks market signals and runs the funnel. Helps launch campaigns and verify they deliver results.",

    // Tariffs
    "home.tariffs.eyebrow": "pricing · per seat",
    "home.tariffs.title": "NXT8 plans",
    "home.tariffs.subtitle":
      "Price per employee per month. Mix plans across teammates and departments.",
    "home.tariffs.popular": "popular pick",
    "home.tariffs.period": "/ employee per month",
    "home.tariffs.cta": "Start",

    "home.plan.personal.f1": "Hermes — main coordinator",
    "home.plan.personal.f2": "Basic company memory",
    "home.plan.personal.f3": "Voice and text interface",
    "home.plan.personal.f4": "Up to 1,000 requests per month",
    "home.plan.team.f1": "Everything in Personal",
    "home.plan.team.f2": "HR-Mentor — people growth",
    "home.plan.team.f3": "Client Operations — work with clients",
    "home.plan.team.f4": "WhatsApp / Telegram integration",
    "home.plan.operations.f1": "Everything in Team",
    "home.plan.operations.f2": "Financial Agent — finance",
    "home.plan.operations.f3": "Legal Review — document review",
    "home.plan.operations.f4": "Marketing Ops — marketing",
    "home.plan.hq.f1": "Everything in Operations",
    "home.plan.hq.f2": "Analytics — team analyst",
    "home.plan.hq.f3": "Project coordinator",
    "home.plan.hq.f4": "Cross-department coordination",
    "home.plan.hq.f5": "Priority support",

    // How it works
    "home.how.eyebrow": "how it works · 3 steps",
    "home.how.title": "How NXT8 works",
    "home.how.step1.title": "Connect your sources",
    "home.how.step1.desc":
      "Chats, documents and the tools your team already uses every day.",
    "home.how.step2.title": "Understanding processes",
    "home.how.step2.desc":
      "NXT8 starts to grasp the company structure, roles and task context with zero manual setup.",
    "home.how.step3.title": "AI team in motion",
    "home.how.step3.desc":
      "AI agents help the team day to day — coordination, answers, follow-up, analytics.",

    // Pilot
    "home.pilot.eyebrow": "free pilot",
    "home.pilot.title.10": "10 teammates",
    "home.pilot.title.14": "14 days",
    "home.pilot.title.free": "free",
    "home.pilot.body1": "Try NXT8 inside your company on real processes and tasks.",
    "home.pilot.body2": "No long contracts. No heavy rollout. No pressure, no strings.",
    "home.pilot.cta": "Launch the pilot",

    // Hermes inline chat
    "home.hermes.eyebrow": "try it now · hermes",
    "home.hermes.title": "Talk to the coordinator",
    "home.hermes.subtitle": "No sign-up. Right here.",
    "home.hermes.mode.text": "text",
    "home.hermes.mode.voice": "voice",
    "home.hermes.send": "send",
    "home.hermes.placeholder": "Write to Hermes…",
    "home.hermes.thinking": "hermes is thinking…",
    "home.hermes.error": "Hermes is unavailable right now. Try again in a minute.",
    "home.hermes.welcome":
      "Hi! I'm Hermes — the main NXT8 coordinator. Ask me anything about your team, or have me help you plan the day.",
    "home.hermes.empty_reply": "Couldn't get a reply — please try again.",

    // Voice (HomeView stub + MicView)
    "voice.idle": "tap to record",
    "voice.recording": "recording… tap to stop",
    "voice.processing": "processing…",
    "voice.synthesizing": "preparing voice…",
    "voice.speaking": "hermes is speaking",
    "voice.error.mic": "Microphone unavailable — allow access in your browser",
    "voice.error.process": "Couldn't process the recording",

    "voice.status.idle": "Ready",
    "voice.status.requesting": "Asking for microphone…",
    "voice.status.recording": "Listening…",
    "voice.status.processing": "Transcribing and processing…",
    "voice.status.speaking": "Speaking",
    "voice.status.error": "Error",
    "voice.too_short": "Recording too short",
    "voice.mic.aria.start": "Start recording",
    "voice.mic.aria.stop": "Stop recording",
    "voice.you_said": "You said",
    "voice.module_caption":
      "Whisper (STT) → Hermes COO → OpenAI TTS. Tap the mic and speak — after 3 seconds of silence the request is sent automatically.",

    // ChatPanel
    "chat.welcome":
      "I'm NXT8. Ask about corporate knowledge, ROI, employees and tasks. Every answer comes with a confidence score and verification against company memory.",
    "chat.placeholder": "Ask NXT8…",
    "chat.thinking": "thinking",
    "chat.empty_reply": "(empty reply)",
    "chat.error.connect": "Connection error: {err}",

    // ChatView header
    "chat.cmd.console": "cmd.console",
    "chat.cmd.session": "full session",

    // Alerts
    "alerts.title": "alerts.feed",
    "alerts.events": "{n} events",
    "alerts.empty": "all quiet — no alerts",

    // Map
    "map.title": "roi.map · hourly",
    "map.alert": "ALERT",
    "map.stable": "stable",
    "map.cost.title": "cost.by_agent",
    "map.trend.title": "roi.trend · 24h",
    "map.trend.hours": "{n} hours",
    "map.no_data": "no data for this hour",
    "map.trend.collecting": "collecting data…",

    // Agents view (personas)
    "agents.team.title": "agents.team",
    "agents.welcome": "Hi. I'm {name}. {role}.\n\nWhat would you like to look into?",
    "agents.locked":
      "Agent \"{name}\" is available on the \"{minPlan}\" plan and higher. Current: \"{plan}\".",
    "agents.plan_required":
      "This agent is available only on the \"{plan}\" plan or higher.",
    "agents.typing": "{name} is typing…",
    "agents.empty_reply": "(empty reply)",
    "agents.error": "Error",
    "agents.ask_placeholder": "Ask {name}…",
    "agents.footer":
      "Hermes is the heart of the system. The other personas share the same memory and tools in a focused role. Plan gates are real — the API returns 402 when a persona is not in the plan.",

    // Ops widgets
    "ops.cockpit": "ops.cockpit",
    "ops.live": "live · 6 modules",
    "ops.crossdept.no_coord": "no coordinations yet",
    "ops.skills.top": "top: {name}",
    "ops.skills.empty": "no skills yet",
    "ops.market.no_signals": "no signals",
    "ops.market.awaiting": "awaiting scan",
    "ops.market.digest_on": "digest {date}",
    "ops.hermes.jobs": "{n} active jobs",
    "ops.hermes.offline": "gateway not running (port 8642)",
    "ops.docs.upload_first": "upload your first document",

    // Ops · Documents
    "ops.docs.title": "documents · compliance",
    "ops.docs.upload.too_large": "File larger than {n} MB",
    "ops.docs.upload.uploading": "uploading · {name}",
    "ops.docs.upload.done": "done · severity={sev}",
    "ops.docs.upload.drop": "drop a PDF / DOCX / TXT (≤ {n} MB)",
    "ops.docs.upload.analyzing": "analysing…",
    "ops.docs.upload.choose": "choose file",
    "ops.docs.uploaded": "uploaded documents",
    "ops.docs.no_risks": "no risks detected",
    "ops.docs.mock_provider": "mock · provider unavailable",
    "ops.docs.empty": "no documents uploaded yet",
    "ops.docs.footer":
      "Documents are parsed locally (pypdf / python-docx), sent to DeepSeek for a compliance review and indexed in MemPalace under wing=documents.",
    "ops.docs.expand": "details",
    "ops.docs.collapse": "collapse",

    // Ops · Cross-dept
    "ops.crossdept.title": "cross-dept · coordinator",
    "ops.crossdept.placeholder":
      "Query touching several departments… (e.g. 'how are we doing on sales and support?'). Ctrl/⌘+Enter to send",
    "ops.crossdept.coordinating": "coordinating…",
    "ops.crossdept.coordinate": "coordinate",
    "ops.crossdept.empty": "no coordinations yet — kick off the first one",
    "ops.crossdept.recent": "recent tasks",
    "ops.crossdept.items": "{n} items",

    // Ops · Diagnostics
    "ops.diag.title": "diagnostics · self-audit",
    "ops.diag.empty": "no contradictions found",
    "ops.diag.found": "{n} found",
    "ops.diag.rescan": "rescan",
    "ops.diag.scanning": "scanning…",

    // Ops · Skills
    "ops.skills.title": "skills · creator",
    "ops.skills.empty.hint":
      "no skills yet — run Discover to auto-detect recurring patterns",
    "ops.skills.registered": "registered skills",
    "ops.skills.discover": "discover",
    "ops.skills.scanning": "scanning…",

    // Ops · Market
    "ops.market.title": "market · radar",
    "ops.market.headline.placeholder":
      "headline (e.g. 'Competitor X launched a free tier')",
    "ops.market.empty": "no signals — add the first one or wait for the auto-feed",
    "ops.market.signals": "signals",
    "ops.market.ingested": "{n} ingested",
    "ops.market.scanning": "scanning…",
    "ops.market.scan_24h": "scan 24h",
    "ops.market.latest_digest": "latest digest · {n} signals",
    "ops.market.digest_history": "digest history",
    "ops.market.add_signal": "add signal",

    // Ops · Hermes
    "ops.hermes.title": "hermes · agent",
    "ops.hermes.empty": "no background jobs — create the first one",
    "ops.hermes.create": "create job",
    "ops.hermes.prompt.placeholder":
      "prompt for the background job (Hermes runs it asynchronously)",
    "ops.hermes.cron.placeholder": "cron (optional, e.g. 0 9 * * *)",
    "ops.hermes.scheduled": "scheduled jobs",
    "ops.hermes.jobs_count": "{n} jobs",
    "ops.hermes.unreachable":
      "Hermes API is unreachable. Start the hermes gateway with API_SERVER_ENABLED=true on port 8642.",
    "ops.hermes.error.unavailable":
      "Hermes unavailable ({code}): {msg}",
    "ops.hermes.error.gateway_hint":
      "check that the hermes gateway is running on :8642",
    "ops.hermes.footer":
      "Hermes Agent (NousResearch) is a self-learning CLI agent with tool calling. In NXT8 it serves as an extra background-job executor via the OpenAI-compatible API.",
    "ops.hermes.submitting": "submitting…",
    "ops.hermes.submit": "submit",

    // Common UI verbs
    "ui.refresh": "refresh",
    "ui.cancel": "cancel",
    "ui.back_to_ops": "← back to ops",
  },

  ru: {
    // Burger menu
    "menu.title": "МЕНЮ",
    "menu.auth": "Авторизация",
    "menu.lang": "Языки",
    "menu.about": "О проекте",
    "menu.support": "Поддержка",
    "menu.settings": "Настройки",
    "menu.pricing": "Тарифы",
    "menu.back": "назад",
    "menu.placeholder": "Блок-заглушка · подключим позже",
    "menu.auth.body": "Здесь будет вход и регистрация.",
    "menu.lang.body": "Переключение языка интерфейса.",
    "menu.lang.current": "Текущий язык",
    "menu.lang.note":
      "Применяется к интерфейсу, чату с Hermes и голосовому режиму (STT + TTS).",
    "menu.lang.english": "Английский",
    "menu.lang.russian": "Русский",
    "menu.about.body": "Информация о NXT8.PRO.",
    "menu.support.body": "Контакты поддержки и форма обращения.",
    "menu.settings.admin": "Вход для администратора",
    "menu.settings.admin.body": "PIN-код 4 цифры · подключим позже",
    "menu.settings.client": "Настройки экрана и клиента",

    "pricing.individual": "Individual",
    "pricing.individual.desc": "Для независимых специалистов и авторов.",
    "pricing.individual.monthly": "$28 в месяц",
    "pricing.individual.annual": "$20 в год",
    "pricing.team": "Team",
    "pricing.team.desc": "Для компаний и распределённых команд.",
    "pricing.team.monthly": "от $18 за сотрудника / месяц",
    "pricing.team.annual": "от $14 при годовой оплате",

    // Seed error
    "seed.error": "backend недоступен — проверьте сервер",

    // Home — tickers
    "home.ticker.hero.1": "Добро пожаловать в NXT8",
    "home.ticker.hero.2": "AI-координация для современной команды",
    "home.ticker.hero.3": "Работает внутри ваших процессов",
    "home.ticker.hero.4": "Меньше хаоса · Больше координации",
    "home.ticker.hero.5": "Без сложного внедрения",
    "home.ticker.features.documents": "Документы",
    "home.ticker.features.tasks": "Задачи",
    "home.ticker.features.calendar": "Календарь",
    "home.ticker.features.together": "Всё работает вместе",
    "home.ticker.pilot.1": "Подключите первых 10 сотрудников бесплатно",
    "home.ticker.pilot.2": "Диагностический пилот — 14 дней",
    "home.ticker.pilot.3": "Без долгих контрактов",
    "home.ticker.pilot.4": "Без обязательств",

    // Home — intro card
    "home.intro.eyebrow": "operational ai system",
    "home.intro.title.before": "Операционная AI-система",
    "home.intro.title.accent": "для современного бизнеса",
    "home.intro.body":
      "Готовая AI-команда, которая работает вместе с вашей компанией. Меньше хаоса. Больше координации. Без сложного внедрения.",
    "home.intro.cta": "выберите AI-агентов",

    // Agents
    "home.agent.label": "agent",
    "home.agent.cta": "Подключить",
    "home.agent.hermes.role": "Главный операционный координатор",
    "home.agent.hermes.plan": "Personal — $9 / сотрудник",
    "home.agent.hermes.desc":
      "Координирует задачи, фиксирует договорённости, помогает команде не терять контекст и связывает процессы компании в единую систему.",
    "home.agent.hr.role": "Развитие сотрудников",
    "home.agent.hr.plan": "Team — $14 / сотрудник",
    "home.agent.hr.desc":
      "Помогает каждому в команде расти. Замечает паттерны выгорания, подсказывает зоны роста и подбирает индивидуальный план развития.",
    "home.agent.client.role": "Менеджер по клиентам",
    "home.agent.client.plan": "Team — $14 / сотрудник",
    "home.agent.client.desc":
      "Ведёт переписку с клиентами, не теряет сделки в потоке, предлагает шаблоны ответов и фиксирует договорённости в CRM.",
    "home.agent.analytics.role": "Аналитик команды",
    "home.agent.analytics.plan": "Headquarters — $24 / сотрудник",
    "home.agent.analytics.desc":
      "Собирает данные из всех источников и показывает, что происходит в компании прямо сейчас. Простые ответы вместо сложных дашбордов.",
    "home.agent.financial.role": "Финансовый помощник",
    "home.agent.financial.plan": "Operations — $19 / сотрудник",
    "home.agent.financial.desc":
      "Контролирует движение денег, напоминает про платежи и помогает планировать бюджет без таблиц и ручных подсчётов.",
    "home.agent.legal.role": "Compliance с разбором документов",
    "home.agent.legal.plan": "Operations — $19 / сотрудник",
    "home.agent.legal.desc":
      "Читает договоры, политики и оферты. Подсвечивает рисковые пункты и предлагает, что согласовать перед подписью.",
    "home.agent.marketing.role": "Маркетолог",
    "home.agent.marketing.plan": "Operations — $19 / сотрудник",
    "home.agent.marketing.desc":
      "Отслеживает рыночные сигналы и работает с воронкой. Помогает запускать кампании и проверять, что они дают результат.",

    // Tariffs
    "home.tariffs.eyebrow": "pricing · per seat",
    "home.tariffs.title": "Тарифы NXT8",
    "home.tariffs.subtitle":
      "Цена за одного сотрудника в месяц. Компания может комбинировать тарифы между сотрудниками и отделами.",
    "home.tariffs.popular": "популярный выбор",
    "home.tariffs.period": "/ сотрудник в месяц",
    "home.tariffs.cta": "Начать",

    "home.plan.personal.f1": "Hermes — главный координатор",
    "home.plan.personal.f2": "Базовая память компании",
    "home.plan.personal.f3": "Голосовой и текстовый интерфейс",
    "home.plan.personal.f4": "До 1 000 запросов в месяц",
    "home.plan.team.f1": "Всё из Personal",
    "home.plan.team.f2": "HR-Mentor — развитие сотрудников",
    "home.plan.team.f3": "Client Operations — работа с клиентами",
    "home.plan.team.f4": "Интеграция WhatsApp / Telegram",
    "home.plan.operations.f1": "Всё из Team",
    "home.plan.operations.f2": "Financial Agent — финансы",
    "home.plan.operations.f3": "Legal Review — разбор документов",
    "home.plan.operations.f4": "Marketing Ops — маркетинг",
    "home.plan.hq.f1": "Всё из Operations",
    "home.plan.hq.f2": "Analytics — аналитик команды",
    "home.plan.hq.f3": "Координатор проектов",
    "home.plan.hq.f4": "Кросс-департаментная координация",
    "home.plan.hq.f5": "Приоритетная поддержка",

    // How it works
    "home.how.eyebrow": "how it works · 3 steps",
    "home.how.title": "Как работает NXT8",
    "home.how.step1.title": "Подключаем источники",
    "home.how.step1.desc":
      "Чаты, документы и рабочие инструменты, которыми пользуется команда каждый день.",
    "home.how.step2.title": "Понимание процессов",
    "home.how.step2.desc":
      "NXT8 начинает понимать структуру компании, роли и контекст задач без ручной настройки.",
    "home.how.step3.title": "AI-команда в работе",
    "home.how.step3.desc":
      "AI-агенты помогают команде в ежедневных задачах — координация, ответы, контроль, аналитика.",

    // Pilot
    "home.pilot.eyebrow": "free pilot",
    "home.pilot.title.10": "10 сотрудников",
    "home.pilot.title.14": "14 дней",
    "home.pilot.title.free": "бесплатно",
    "home.pilot.body1": "Проверьте NXT8 внутри вашей компании на реальных процессах и задачах.",
    "home.pilot.body2":
      "Без долгих контрактов. Без сложного внедрения. Без давления и обязательств.",
    "home.pilot.cta": "Запустить пилот",

    // Hermes inline chat
    "home.hermes.eyebrow": "try it now · hermes",
    "home.hermes.title": "Поговорите с координатором",
    "home.hermes.subtitle": "Без регистрации. Сразу здесь.",
    "home.hermes.mode.text": "текст",
    "home.hermes.mode.voice": "голос",
    "home.hermes.send": "send",
    "home.hermes.placeholder": "Напишите Hermes…",
    "home.hermes.thinking": "hermes думает…",
    "home.hermes.error": "Сейчас Hermes недоступен. Попробуйте через минуту.",
    "home.hermes.welcome":
      "Привет! Я Hermes — главный координатор NXT8. Спросите что-нибудь о вашей команде, или попросите помочь спланировать день.",
    "home.hermes.empty_reply": "Не получилось получить ответ — попробуйте ещё раз.",

    // Voice
    "voice.idle": "нажмите чтобы записать",
    "voice.recording": "запись… нажмите чтобы остановить",
    "voice.processing": "обработка…",
    "voice.synthesizing": "озвучиваю…",
    "voice.speaking": "hermes говорит",
    "voice.error.mic": "Микрофон недоступен — разрешите доступ в браузере",
    "voice.error.process": "Не удалось обработать запись",

    "voice.status.idle": "Готов",
    "voice.status.requesting": "Запрос микрофона…",
    "voice.status.recording": "Слушаю…",
    "voice.status.processing": "Распознаю и обрабатываю…",
    "voice.status.speaking": "Отвечаю",
    "voice.status.error": "Ошибка",
    "voice.too_short": "Слишком короткая запись",
    "voice.mic.aria.start": "Начать запись",
    "voice.mic.aria.stop": "Остановить запись",
    "voice.you_said": "Вы сказали",
    "voice.module_caption":
      "Whisper (STT) → Hermes COO → OpenAI TTS. Тапните на микрофон и говорите — после 3 секунд тишины запрос уйдёт агенту автоматически.",

    // ChatPanel
    "chat.welcome":
      "Я NXT8. Спрашивайте про корпоративные знания, ROI, сотрудников и задачи. Каждый мой ответ сопровождается confidence score и проверкой против корпоративной памяти.",
    "chat.placeholder": "Спросите NXT8…",
    "chat.thinking": "думаю",
    "chat.empty_reply": "(пустой ответ)",
    "chat.error.connect": "Ошибка соединения: {err}",

    // ChatView header
    "chat.cmd.console": "cmd.console",
    "chat.cmd.session": "full session",

    // Alerts
    "alerts.title": "alerts.feed",
    "alerts.events": "{n} событий",
    "alerts.empty": "всё спокойно — алертов нет",

    // Map
    "map.title": "roi.map · hourly",
    "map.alert": "ALERT",
    "map.stable": "stable",
    "map.cost.title": "cost.by_agent",
    "map.trend.title": "roi.trend · 24h",
    "map.trend.hours": "{n} часов",
    "map.no_data": "нет данных за час",
    "map.trend.collecting": "накапливаю данные…",

    // Agents view (personas)
    "agents.team.title": "agents.team",
    "agents.welcome": "Привет. Я — {name}. {role}.\n\nЧто разобрать?",
    "agents.locked":
      "Агент «{name}» доступен на тарифе «{minPlan}» и выше. Текущий: «{plan}».",
    "agents.plan_required":
      "Этот агент доступен только на тарифе «{plan}» или выше.",
    "agents.typing": "{name} печатает…",
    "agents.empty_reply": "(пустой ответ)",
    "agents.error": "Ошибка",
    "agents.ask_placeholder": "Спросите {name}…",
    "agents.footer":
      "Hermes — сердце системы. Остальные персоны опираются на ту же память и инструменты, но в фокусированной роли. Тарифные ворота — реальные: API возвращает 402, если персона не включена в план.",

    // Ops widgets
    "ops.cockpit": "ops.cockpit",
    "ops.live": "live · 6 модулей",
    "ops.crossdept.no_coord": "пока нет координаций",
    "ops.skills.top": "top: {name}",
    "ops.skills.empty": "навыков ещё нет",
    "ops.market.no_signals": "нет сигналов",
    "ops.market.awaiting": "ожидание скана",
    "ops.market.digest_on": "digest {date}",
    "ops.hermes.jobs": "{n} активных заданий",
    "ops.hermes.offline": "gateway не запущен (порт 8642)",
    "ops.docs.upload_first": "загрузите первый документ",

    // Ops · Documents
    "ops.docs.title": "documents · compliance",
    "ops.docs.upload.too_large": "Файл больше {n} MB",
    "ops.docs.upload.uploading": "загружаю · {name}",
    "ops.docs.upload.done": "готово · severity={sev}",
    "ops.docs.upload.drop": "перетащите PDF / DOCX / TXT (≤ {n} MB)",
    "ops.docs.upload.analyzing": "анализ…",
    "ops.docs.upload.choose": "выбрать файл",
    "ops.docs.uploaded": "uploaded documents",
    "ops.docs.no_risks": "рисков не обнаружено",
    "ops.docs.mock_provider": "mock · provider недоступен",
    "ops.docs.empty": "пока нет загруженных документов",
    "ops.docs.footer":
      "Документ парсится локально (pypdf / python-docx), отправляется в DeepSeek для compliance-обзора и индексируется в MemPalace под wing=documents.",
    "ops.docs.expand": "детали",
    "ops.docs.collapse": "свернуть",

    // Ops · Cross-dept
    "ops.crossdept.title": "cross-dept · coordinator",
    "ops.crossdept.placeholder":
      "Запрос, затрагивающий несколько отделов… (например: «что у нас по продажам и поддержке?»). Ctrl/⌘+Enter — отправить",
    "ops.crossdept.coordinating": "координирую…",
    "ops.crossdept.coordinate": "coordinate",
    "ops.crossdept.empty": "ещё не было координаций — запустите первую",
    "ops.crossdept.recent": "recent tasks",
    "ops.crossdept.items": "{n} items",

    // Ops · Diagnostics
    "ops.diag.title": "diagnostics · self-audit",
    "ops.diag.empty": "противоречий не обнаружено",
    "ops.diag.found": "{n} found",
    "ops.diag.rescan": "rescan",
    "ops.diag.scanning": "scanning…",

    // Ops · Skills
    "ops.skills.title": "skills · creator",
    "ops.skills.empty.hint":
      "пока навыков нет — запустите discover для авто-обнаружения повторяющихся паттернов",
    "ops.skills.registered": "registered skills",
    "ops.skills.discover": "discover",
    "ops.skills.scanning": "scanning…",

    // Ops · Market
    "ops.market.title": "market · radar",
    "ops.market.headline.placeholder":
      "headline (например: «Конкурент X запустил free-tier»)",
    "ops.market.empty": "нет сигналов — добавьте первый или дождитесь авто-фида",
    "ops.market.signals": "signals",
    "ops.market.ingested": "{n} ingested",
    "ops.market.scanning": "scanning…",
    "ops.market.scan_24h": "scan 24h",
    "ops.market.latest_digest": "latest digest · {n} signals",
    "ops.market.digest_history": "digest history",
    "ops.market.add_signal": "add signal",

    // Ops · Hermes
    "ops.hermes.title": "hermes · agent",
    "ops.hermes.empty": "нет фоновых заданий — создайте первое",
    "ops.hermes.create": "создать задание",
    "ops.hermes.prompt.placeholder":
      "prompt для фонового задания (Hermes выполнит асинхронно)",
    "ops.hermes.cron.placeholder": "cron (опционально, например: 0 9 * * *)",
    "ops.hermes.scheduled": "scheduled jobs",
    "ops.hermes.jobs_count": "{n} jobs",
    "ops.hermes.unreachable":
      "Hermes API недоступен. Запустите hermes gateway с API_SERVER_ENABLED=true на порту 8642.",
    "ops.hermes.error.unavailable":
      "Hermes недоступен ({code}): {msg}",
    "ops.hermes.error.gateway_hint":
      "проверьте, что hermes gateway запущен на :8642",
    "ops.hermes.footer":
      "Hermes Agent (NousResearch) — самообучающийся CLI-агент с tool calling. В NXT8 используется как доп. исполнитель фоновых заданий через OpenAI-совместимое API.",
    "ops.hermes.submitting": "submitting…",
    "ops.hermes.submit": "submit",

    // Common UI verbs
    "ui.refresh": "refresh",
    "ui.cancel": "cancel",
    "ui.back_to_ops": "← назад в ops",
  },
};

export const DEFAULT_LANG = "en";
export const SUPPORTED_LANGS = ["en", "ru"];
