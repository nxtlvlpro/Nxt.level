import React, { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "./ui/sheet";
import {
  LogIn,
  Languages,
  Info,
  LifeBuoy,
  Settings as SettingsIcon,
  Tag,
  ChevronRight,
  ArrowLeft,
  Check,
  Terminal,
  LayoutGrid,
  GitBranch,
  Activity,
} from "lucide-react";
import { useT } from "../i18n/LanguageContext";

// Secondary nav targets — these used to live in `BottomNav` but were
// evicted to keep the mobile bottom bar at exactly 5 icons on 360 px.
const NAV_TARGETS = [
  { id: "cmd",   label: "Command line", icon: Terminal },
  { id: "ops",   label: "Operations",   icon: LayoutGrid },
  { id: "graph", label: "Graph",        icon: GitBranch },
  { id: "os",    label: "Hermes OS",    icon: Activity },
];

const MENU_KEYS = [
  { key: "auth", labelKey: "menu.auth", icon: LogIn },
  { key: "lang", labelKey: "menu.lang", icon: Languages },
  { key: "about", labelKey: "menu.about", icon: Info },
  { key: "support", labelKey: "menu.support", icon: LifeBuoy },
  { key: "settings", labelKey: "menu.settings", icon: SettingsIcon },
  { key: "pricing", labelKey: "menu.pricing", icon: Tag },
];

function MenuList({ onSelect, t }) {
  return (
    <ul className="space-y-1" data-testid="burger-menu-list">
      {MENU_KEYS.map(({ key, labelKey, icon: Icon }) => (
        <li key={key}>
          <button
            type="button"
            onClick={() => onSelect(key)}
            data-testid={`burger-item-${key}`}
            className="w-full flex items-center justify-between px-4 py-4 text-left bg-white/[0.02] hover:bg-brand-turquoise/10 border border-white/5 hover:border-brand-turquoise/40 rounded-md transition-colors group"
          >
            <span className="flex items-center gap-3">
              <Icon className="w-4 h-4 text-brand-turquoise/80 group-hover:text-brand-turquoise" />
              <span className="tracking-wide text-slate-200 group-hover:text-white text-sm">
                {t(labelKey)}
              </span>
            </span>
            <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-brand-turquoise" />
          </button>
        </li>
      ))}
    </ul>
  );
}

function SectionShell({ title, children }) {
  return (
    <div className="space-y-4" data-testid={`burger-section-${title.toLowerCase()}`}>
      <h3 className="text-sm tracking-[0.25em] uppercase text-brand-turquoise/90 font-light">
        {title}
      </h3>
      <div className="text-sm text-slate-300 leading-relaxed space-y-3">
        {children}
      </div>
    </div>
  );
}

function PricingTier({ name, prices, description, testIdKey }) {
  return (
    <div
      className="border border-white/10 rounded-md p-5 bg-white/[0.02]"
      data-testid={`pricing-tier-${testIdKey}`}
    >
      <h4 className="text-2xl font-light text-white tracking-wide mb-4">
        {name}
      </h4>
      <ul className="space-y-2 mb-4">
        {prices.map((p) => (
          <li key={p} className="flex items-start gap-2 text-base text-slate-200 font-light">
            <span className="text-brand-turquoise mt-2 w-1 h-1 rounded-full bg-brand-turquoise flex-shrink-0" />
            <span>{p}</span>
          </li>
        ))}
      </ul>
      <p className="text-sm text-slate-400 font-light">{description}</p>
    </div>
  );
}

function AuthBlock({ t }) {
  return (
    <SectionShell title={t("menu.auth")}>
      <p className="text-slate-400">{t("menu.auth.body")}</p>
      <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
        {t("menu.placeholder")}
      </div>
    </SectionShell>
  );
}

function LangBlock({ t, lang, setLang }) {
  const OPTIONS = [
    { code: "en", labelKey: "menu.lang.english",    native: "English" },
    { code: "ru", labelKey: "menu.lang.russian",    native: "Русский" },
    { code: "es", labelKey: "menu.lang.spanish",    native: "Español" },
    { code: "fr", labelKey: "menu.lang.french",     native: "Français" },
    { code: "de", labelKey: "menu.lang.german",     native: "Deutsch" },
    { code: "pt", labelKey: "menu.lang.portuguese", native: "Português" },
    { code: "it", labelKey: "menu.lang.italian",    native: "Italiano" },
    { code: "zh", labelKey: "menu.lang.chinese",    native: "中文" },
    { code: "ja", labelKey: "menu.lang.japanese",   native: "日本語" },
    { code: "tr", labelKey: "menu.lang.turkish",    native: "Türkçe" },
  ];
  return (
    <SectionShell title={t("menu.lang")}>
      <p className="text-slate-400">{t("menu.lang.body")}</p>
      <div
        className="text-[10px] uppercase tracking-widest text-slate-500"
        data-testid="lang-current-label"
      >
        {t("menu.lang.current")}
      </div>
      <div className="space-y-2" data-testid="lang-options">
        {OPTIONS.map(({ code, labelKey, native }) => {
          const active = lang === code;
          return (
            <button
              key={code}
              type="button"
              onClick={() => setLang(code)}
              data-testid={`lang-option-${code}`}
              aria-pressed={active}
              className={`w-full flex items-center justify-between px-4 py-3 rounded-md border transition-colors text-left ${
                active
                  ? "bg-brand-turquoise/10 border-brand-turquoise/50 text-white"
                  : "bg-white/[0.02] border-white/5 text-slate-300 hover:border-brand-turquoise/30 hover:text-white"
              }`}
            >
              <span className="flex items-center gap-3">
                <span
                  className={`w-7 h-7 rounded-md border flex items-center justify-center text-[10px] uppercase tracking-widest ${
                    active
                      ? "border-brand-turquoise/60 text-brand-turquoise"
                      : "border-white/10 text-slate-500"
                  }`}
                >
                  {code}
                </span>
                <span className="flex flex-col">
                  <span className="text-sm tracking-wide">{native}</span>
                  <span className="text-[10px] uppercase tracking-widest text-slate-500">
                    {t(labelKey)}
                  </span>
                </span>
              </span>
              {active && (
                <Check className="w-4 h-4 text-brand-turquoise" />
              )}
            </button>
          );
        })}
      </div>
      <p className="text-[11px] text-slate-500 leading-relaxed pt-1">
        {t("menu.lang.note")}
      </p>
    </SectionShell>
  );
}

function AboutBlock({ t }) {
  return (
    <SectionShell title={t("menu.about")}>
      <p className="text-slate-400">{t("menu.about.body")}</p>
      <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
        {t("menu.placeholder")}
      </div>
    </SectionShell>
  );
}

function SupportBlock({ t }) {
  return (
    <SectionShell title={t("menu.support")}>
      <p className="text-slate-400">{t("menu.support.body")}</p>
      <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
        {t("menu.placeholder")}
      </div>
    </SectionShell>
  );
}

function SettingsBlock({ t }) {
  return (
    <SectionShell title={t("menu.settings")}>
      <div className="space-y-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">
            {t("menu.settings.admin")}
          </div>
          <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
            {t("menu.settings.admin.body")}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">
            {t("menu.settings.client")}
          </div>
          <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
            {t("menu.placeholder")}
          </div>
        </div>
      </div>
    </SectionShell>
  );
}

function PricingBlock({ t }) {
  return (
    <SectionShell title={t("menu.pricing")}>
      <PricingTier
        name={t("pricing.individual")}
        prices={[t("pricing.individual.monthly"), t("pricing.individual.annual")]}
        description={t("pricing.individual.desc")}
        testIdKey="individual"
      />
      <div className="border-t border-white/10 my-4" />
      <PricingTier
        name={t("pricing.team")}
        prices={[t("pricing.team.monthly"), t("pricing.team.annual")]}
        description={t("pricing.team.desc")}
        testIdKey="team"
      />
    </SectionShell>
  );
}

const SECTION_BLOCKS = {
  auth: AuthBlock,
  lang: LangBlock,
  about: AboutBlock,
  support: SupportBlock,
  settings: SettingsBlock,
  pricing: PricingBlock,
};

export default function BurgerMenu({ open, onOpenChange, onNavigate }) {
  const [active, setActive] = useState(null);
  const { t, lang, setLang } = useT();

  const handleOpenChange = (next) => {
    if (!next) setActive(null);
    onOpenChange(next);
  };

  const handleNavigate = (viewId) => {
    onNavigate?.(viewId);
    handleOpenChange(false);
  };

  const ActiveBlock = active ? SECTION_BLOCKS[active] : null;
  const activeMeta = active ? MENU_KEYS.find((i) => i.key === active) : null;
  const activeLabel = activeMeta ? t(activeMeta.labelKey) : null;

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        className="bg-black border-l border-brand-turquoise/20 text-white w-[88vw] sm:max-w-md p-0 flex flex-col"
        data-testid="burger-sheet"
      >
        <SheetHeader className="px-5 pt-5 pb-3 border-b border-white/5">
          <div className="flex items-center gap-3">
            {active && (
              <button
                type="button"
                onClick={() => setActive(null)}
                className="text-slate-400 hover:text-brand-turquoise"
                aria-label={t("menu.back")}
                data-testid="burger-back"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            )}
            <SheetTitle className="text-white text-base tracking-[0.3em] font-light">
              {active ? activeLabel : t("menu.title")}
            </SheetTitle>
          </div>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
          {ActiveBlock ? (
            <ActiveBlock t={t} lang={lang} setLang={setLang} />
          ) : (
            <>
              {/* Secondary nav targets — only visible on mobile where
                  BottomNav now caps at 5 icons. Hidden on lg+ since the
                  sidebar exposes everything already. */}
              {onNavigate && (
                <div className="lg:hidden">
                  <div className="text-[10px] uppercase tracking-[0.3em] text-slate-500 mb-2 px-1">
                    Разделы
                  </div>
                  <ul className="space-y-1" data-testid="burger-nav-list">
                    {NAV_TARGETS.map(({ id, label, icon: Icon }) => (
                      <li key={id}>
                        <button
                          type="button"
                          onClick={() => handleNavigate(id)}
                          data-testid={`burger-nav-${id}`}
                          className="w-full flex items-center justify-between px-4 py-3.5 text-left bg-white/[0.02] hover:bg-brand-turquoise/10 border border-white/5 hover:border-brand-turquoise/40 rounded-md transition-colors group"
                        >
                          <span className="flex items-center gap-3">
                            <Icon className="w-4 h-4 text-brand-turquoise/80 group-hover:text-brand-turquoise" />
                            <span className="tracking-wide text-slate-200 group-hover:text-white text-sm">
                              {label}
                            </span>
                          </span>
                          <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-brand-turquoise" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                {onNavigate && (
                  <div className="text-[10px] uppercase tracking-[0.3em] text-slate-500 mb-2 px-1 lg:hidden">
                    Настройки
                  </div>
                )}
                <MenuList onSelect={setActive} t={t} />
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
