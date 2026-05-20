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
} from "lucide-react";

const MENU_ITEMS = [
  { key: "auth", label: "Авторизация", icon: LogIn },
  { key: "lang", label: "Языки", icon: Languages },
  { key: "about", label: "О проекте", icon: Info },
  { key: "support", label: "Поддержка", icon: LifeBuoy },
  { key: "settings", label: "Настройки", icon: SettingsIcon },
  { key: "pricing", label: "Тарифы", icon: Tag },
];

function MenuList({ onSelect }) {
  return (
    <ul className="space-y-1" data-testid="burger-menu-list">
      {MENU_ITEMS.map(({ key, label, icon: Icon }) => (
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
                {label}
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

function PricingTier({ name, prices, description }) {
  return (
    <div
      className="border border-white/10 rounded-md p-5 bg-white/[0.02]"
      data-testid={`pricing-tier-${name.toLowerCase()}`}
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

function AuthBlock() {
  return (
    <SectionShell title="Авторизация">
      <p className="text-slate-400">
        Здесь будет вход и регистрация.
      </p>
      <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
        Блок-заглушка · подключим позже
      </div>
    </SectionShell>
  );
}

function LangBlock() {
  return (
    <SectionShell title="Языки">
      <p className="text-slate-400">
        Переключение языка интерфейса.
      </p>
      <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
        Блок-заглушка · подключим позже
      </div>
    </SectionShell>
  );
}

function AboutBlock() {
  return (
    <SectionShell title="О проекте">
      <p className="text-slate-400">
        Информация о NXT8.PRO.
      </p>
      <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
        Блок-заглушка · подключим позже
      </div>
    </SectionShell>
  );
}

function SupportBlock() {
  return (
    <SectionShell title="Поддержка">
      <p className="text-slate-400">
        Контакты поддержки и форма обращения.
      </p>
      <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
        Блок-заглушка · подключим позже
      </div>
    </SectionShell>
  );
}

function SettingsBlock() {
  return (
    <SectionShell title="Настройки">
      <div className="space-y-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">
            Вход для администратора
          </div>
          <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
            PIN-код 4 цифры · подключим позже
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">
            Настройки экрана и клиента
          </div>
          <div className="border border-dashed border-white/10 rounded-md p-4 text-slate-500 text-xs uppercase tracking-widest">
            Блок-заглушка · подключим позже
          </div>
        </div>
      </div>
    </SectionShell>
  );
}

function PricingBlock() {
  return (
    <SectionShell title="Тарифы">
      <PricingTier
        name="Individual"
        prices={["$28 monthly", "$20 annual"]}
        description="For independent professionals and creators."
      />
      <div className="border-t border-white/10 my-4" />
      <PricingTier
        name="Team"
        prices={["from $18 per seat/month", "from $14 annual billing"]}
        description="For companies and distributed teams."
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

export default function BurgerMenu({ open, onOpenChange }) {
  const [active, setActive] = useState(null);

  const handleOpenChange = (next) => {
    if (!next) setActive(null);
    onOpenChange(next);
  };

  const ActiveBlock = active ? SECTION_BLOCKS[active] : null;
  const activeLabel = active
    ? MENU_ITEMS.find((i) => i.key === active)?.label
    : null;

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
                aria-label="back"
                data-testid="burger-back"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            )}
            <SheetTitle className="text-white text-base tracking-[0.3em] font-light">
              {active ? activeLabel : "МЕНЮ"}
            </SheetTitle>
          </div>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {ActiveBlock ? <ActiveBlock /> : <MenuList onSelect={setActive} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}
