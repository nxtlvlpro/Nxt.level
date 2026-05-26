import React, { useState } from "react";
import BurgerMenu from "./BurgerMenu";

export default function Header({ aiIndex = 8.1, streakDays = 14 }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <>
      <header
        className="flex justify-between items-center py-1"
        data-testid="app-header"
      >
        <div className="flex items-center space-x-3">
          <div className="w-6 h-6 rounded-md bg-brand-turquoise/20 border border-brand-turquoise/40 flex items-center justify-center">
            <div className="w-3 h-3 bg-brand-turquoise rounded-sm shadow-[0_0_8px_rgba(6,182,212,0.8)]"></div>
          </div>
          <h1
            className="text-2xl tracking-[0.3em] text-white font-light leading-none"
            data-testid="app-title"
          >
            NXT8
          </h1>
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
      <BurgerMenu open={menuOpen} onOpenChange={setMenuOpen} />
    </>
  );
}
