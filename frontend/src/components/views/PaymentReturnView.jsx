import React, { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, XCircle, AlertTriangle, ArrowLeft } from "lucide-react";
import api from "../../lib/api";

const POLL_INTERVAL_MS = 2500;
const MAX_ATTEMPTS = 12; // ~30 s

function getQuery(name) {
  if (typeof window === "undefined") return "";
  const m = new RegExp(`[?&]${name}=([^&#]*)`).exec(window.location.search);
  return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
}

export default function PaymentReturnView() {
  const [phase, setPhase] = useState("checking"); // checking | paid | open | error | timeout
  const [info, setInfo] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const stoppedRef = useRef(false);
  const sessionId = getQuery("session_id");

  useEffect(() => {
    if (!sessionId) {
      setPhase("error");
      return;
    }
    stoppedRef.current = false;
    let attempts = 0;
    const tick = async () => {
      if (stoppedRef.current) return;
      attempts += 1;
      setAttempt(attempts);
      try {
        const data = await api.checkoutStatus(sessionId);
        setInfo(data);
        if (data.payment_status === "paid") {
          setPhase("paid");
          return;
        }
        if (data.status === "expired") {
          setPhase("expired");
          return;
        }
        if (attempts >= MAX_ATTEMPTS) {
          setPhase("timeout");
          return;
        }
        setTimeout(tick, POLL_INTERVAL_MS);
      } catch (e) {
        if (attempts >= MAX_ATTEMPTS) {
          setPhase("error");
          return;
        }
        setTimeout(tick, POLL_INTERVAL_MS);
      }
    };
    tick();
    return () => {
      stoppedRef.current = true;
    };
  }, [sessionId]);

  const goHome = () => {
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
  };

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center bg-brand-dark led-matrix p-6"
      data-testid="payment-return-view"
    >
      <div className="glass-card window-border glow-turquoise-subtle rounded-2xl p-8 max-w-lg w-full text-center">
        <div className="flex justify-center mb-4">
          {phase === "checking" && (
            <Loader2 className="w-12 h-12 text-brand-turquoise animate-spin" />
          )}
          {phase === "paid" && (
            <CheckCircle2 className="w-12 h-12 text-emerald-400" />
          )}
          {phase === "expired" && (
            <XCircle className="w-12 h-12 text-orange-400" />
          )}
          {(phase === "error" || phase === "timeout") && (
            <AlertTriangle className="w-12 h-12 text-amber-400" />
          )}
        </div>
        <h1 className="text-xl font-light text-slate-100 mb-2">
          {phase === "checking" && "Checking your payment…"}
          {phase === "paid" && "Payment received"}
          {phase === "expired" && "Checkout session expired"}
          {phase === "error" && "Something went wrong"}
          {phase === "timeout" &&
            "Still confirming with Stripe — we'll email you the receipt"}
        </h1>
        <p className="text-[12px] text-slate-400 leading-relaxed">
          {phase === "checking" &&
            `Polling Stripe (attempt ${attempt}/${MAX_ATTEMPTS}). This usually takes a few seconds.`}
          {phase === "paid" && info && (
            <>
              Plan: <span className="text-brand-turquoise">{info.metadata?.plan_name || info.metadata?.plan_id || "—"}</span>
              {info.amount_total > 0 && (
                <>
                  {" · "}
                  Amount: <span className="text-slate-200">
                    {(info.amount_total / 100).toFixed(2)} {(info.currency || "usd").toUpperCase()}
                  </span>
                </>
              )}
            </>
          )}
          {phase === "expired" &&
            "Your session expired before payment completed. Start over to try again."}
          {phase === "error" &&
            "We couldn't confirm the payment. If you were charged, our team will see the webhook event and contact you."}
          {phase === "timeout" &&
            "Status checks reached the limit. The Stripe webhook will reconcile this in the background."}
        </p>
        {info?.fallback === "stripe_retrieve_unavailable" && (
          <p className="text-[10px] text-slate-500 mt-3 italic">
            (Live retrieval via Stripe proxy is delayed — relying on the
            webhook to finalise this transaction.)
          </p>
        )}
        <button
          type="button"
          onClick={goHome}
          className="neo-btn rounded-full px-5 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center gap-1.5 mx-auto mt-6"
          data-testid="payment-return-home"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to NXT8
        </button>
      </div>
    </div>
  );
}
