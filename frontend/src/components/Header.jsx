import React, { useState } from "react";
import BurgerMenu from "./BurgerMenu";
import { HEADER_LOCKED } from "../config/header.locked";

// ⚠ HEADER LAYOUT IS LOCKED — see /app/frontend/src/config/header.locked.js
// Do NOT edit logo size / margin / padding here. Update the locked config
// instead, and only with explicit user approval.

export default function Header({ aiIndex = 8.1, streakDays = 14, onNavigate }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <>
      <header
        className={`flex justify-between items-center ${HEADER_LOCKED.headerVerticalPaddingClass}`}
        data-testid="app-header"
      >
        <div className={`flex items-center ${HEADER_LOCKED.logoMarginLeftClass}`}>
          <img
            src={HEADER_LOCKED.logoSrc}
            alt="NXT8"
            data-testid="app-logo"
            className={`${HEADER_LOCKED.logoHeightClass} w-auto select-none pointer-events-none`}
            draggable={false}
          />
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-full border border-brand-turquoise/60 flex items-center justify-center text-[10px] text-orange-400 font-medium">
            A
          </div>
          <div className="w-6 h-6 rounded-full border border-brand-turquoise/60 flex items-center justify-center text-[10px] text-blue-400 font-medium">
            C
          </div>
          <div className="w-6 h-6 rounded-full border border-brand-turquoise/60 flex items-center justify-center text-[10px] text-brand-turquoise font-medium">
            M
          </div>
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            className="ml-2 flex flex-col justify-center space-y-1.5 h-6 cursor-pointer hover:opacity-80 transition-opacity"
            aria-label="menu"
            data-testid="menu-button"
          >
            <div className="w-[25.6px] h-[0.5px] bg-brand-turquoise"></div>
            <div className="w-[25.6px] h-[0.5px] bg-brand-turquoise"></div>
          </button>
        </div>
      </header>
      <BurgerMenu open={menuOpen} onOpenChange={setMenuOpen} onNavigate={onNavigate} />
    </>
  );
}
