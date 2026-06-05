// AppErrorBoundary — last-resort catch for uncaught render errors.
//
// We deliberately do NOT show stack traces or error messages to end-users.
// All technical detail is logged to `console.error` only; production
// telemetry hook is a separate P1 task.

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_error) {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Console-only — never expose to user.
    // eslint-disable-next-line no-console
    console.error("[NXT8] uncaught render error:", error, info);
  }

  handleReload = () => {
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        data-testid="app-error-boundary"
        className="min-h-screen w-screen flex items-center justify-center bg-brand-dark text-slate-200 px-6"
      >
        <div className="max-w-md w-full text-center space-y-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rose-500/10 ring-1 ring-rose-400/30">
            <AlertTriangle className="w-8 h-8 text-rose-300" />
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl sm:text-3xl font-semibold">
              Что-то пошло не так
            </h1>
            <p className="text-sm text-white/50 leading-relaxed">
              Мы уже уведомлены. Попробуйте обновить страницу — обычно
              это решает проблему.
            </p>
          </div>

          <button
            type="button"
            onClick={this.handleReload}
            data-testid="reload-page-btn"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-brand-turquoise/15 ring-1 ring-brand-turquoise/40 text-brand-turquoise hover:bg-brand-turquoise/25 transition font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Обновить страницу
          </button>

          <p className="text-[10px] font-mono text-white/30 tracking-wider">
            NXT8 · ERROR_BOUNDARY
          </p>
        </div>
      </div>
    );
  }
}
