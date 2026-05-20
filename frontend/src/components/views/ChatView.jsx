import React from "react";
import CollapsibleCard from "../CollapsibleCard";
import ChatPanel from "../ChatPanel";

export default function ChatView() {
  return (
    <div className="lg:max-w-4xl lg:mx-auto">
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
  );
}
