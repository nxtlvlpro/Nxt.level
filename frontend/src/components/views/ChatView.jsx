// ChatView — responsive entry point.
//
// • Mobile (< lg)  → full-screen `MobileChatView` (one-hand UX, attachments,
//                    dvh sticky input).
// • Desktop (lg+) → existing CollapsibleCard + ChatPanel layout (untouched
//                    per spec: "Desktop версию не трогать").
//
// We split the two surfaces with Tailwind responsive classes rather than a
// JS media query so SSR / first-paint stays correct.

import React from "react";
import CollapsibleCard from "../CollapsibleCard";
import ChatPanel from "../ChatPanel";
import MobileChatView from "./MobileChatView";

export default function ChatView() {
  return (
    <>
      {/* Mobile: dedicated full-screen chat */}
      <div className="lg:hidden" data-testid="chat-view-mobile">
        <MobileChatView />
      </div>

      {/* Desktop: legacy card layout — DO NOT TOUCH */}
      <div className="hidden lg:block lg:max-w-4xl lg:mx-auto" data-testid="chat-view-desktop">
        <CollapsibleCard
          storageKey="chat-console"
          testId="chat-view"
          title={
            <span className="text-brand-turquoise font-light text-xs">
              cmd.console
            </span>
          }
          titleRight={
            <span className="text-slate-500 text-[10px] uppercase tracking-widest">
              full session
            </span>
          }
          bodyClassName="px-4 pb-4 pt-0"
        >
          <ChatPanel
            heightClassName="h-[62vh] min-h-[420px]"
            sessionPrefix="cmd"
            testIdPrefix="chat"
          />
        </CollapsibleCard>
      </div>
    </>
  );
}
