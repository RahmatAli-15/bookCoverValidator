import { useEffect, useState } from "react";

import { getDatasetStatus } from "../services/coverApi";

const STAGES = [
  "NEW FILE FOUND",
  "UPLOADING",
  "OCR PROCESSING",
  "SAFE-ZONE VALIDATION",
  "BADGE OVERLAP ANALYSIS",
  "QUALITY ANALYSIS",
  "GENERATING ANNOTATIONS",
  "GENERATING AIRTABLE RECORD",
  "GENERATING EMAIL NOTIFICATION",
  "COMPLETED",
];

function StageIcon({ state, stage }) {
  const toneClass = state === "done" ? "text-emerald-700" : state === "active" ? "text-brand-700" : "text-slate-400";
  const base = `h-4 w-4 ${toneClass}`;
  if (stage === "NEW FILE FOUND") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 6h16v12H4z" />
        <path d="M9 10h6M9 14h6" />
      </svg>
    );
  }
  if (stage === "UPLOADING") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 16V6" />
        <path d="M8 10l4-4 4 4" />
        <path d="M4 18h16" />
      </svg>
    );
  }
  if (stage === "OCR PROCESSING") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="6" />
        <path d="M20 20l-4-4" />
      </svg>
    );
  }
  if (stage === "SAFE-ZONE VALIDATION") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 3l7 3v6c0 5-3.5 7.5-7 9-3.5-1.5-7-4-7-9V6l7-3z" />
      </svg>
    );
  }
  if (stage === "BADGE OVERLAP ANALYSIS") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 9v4m0 4h.01" />
        <circle cx="12" cy="12" r="9" />
      </svg>
    );
  }
  if (stage === "QUALITY ANALYSIS") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 18l5-5 3 3 8-8" />
        <path d="M20 10V4h-6" />
      </svg>
    );
  }
  if (stage === "GENERATING ANNOTATIONS") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="4" width="18" height="14" rx="2" />
        <path d="M8 14l2-2 2 2 4-4 2 2" />
      </svg>
    );
  }
  if (stage === "GENERATING AIRTABLE RECORD") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 7h16M4 12h16M4 17h16" />
      </svg>
    );
  }
  if (stage === "GENERATING EMAIL NOTIFICATION") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 6h16v12H4z" />
        <path d="M4 8l8 6 8-6" />
      </svg>
    );
  }
  if (stage === "COMPLETED") {
    return (
      <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M8 12l2.5 2.5L16 9" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className={base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
    </svg>
  );
}

export default function Sidebar() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let active = true;
    let intervalId = null;

    const refresh = async () => {
      try {
        const payload = await getDatasetStatus();
        if (!active) return;
        setStatus(payload);
        const queueCount = payload?.summary?.processing_queue_count ?? 0;
        if (queueCount <= 0 && intervalId) {
          clearInterval(intervalId);
          intervalId = null;
        }
      } catch {
        // keep sidebar lightweight; ignore fetch failures silently
      }
    };

    refresh();
    intervalId = setInterval(refresh, 2000);
    return () => {
      active = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  const currentStage = status?.current_stage || "IDLE";
  const currentFile = status?.current_file || null;
  const stageIdx = STAGES.indexOf(currentStage);
  const isRunning = (status?.summary?.processing_queue_count ?? 0) > 0;
  const isCompleted = currentStage === "COMPLETED" && !isRunning;
  const pipelineStateLabel = isRunning ? "Running" : isCompleted ? "Completed" : "Idle";

  return (
    <aside className="w-full border-r border-slate-200 bg-white p-4 md:w-72">
      <section className="rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Live Pipeline</p>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isRunning ? "bg-brand-100 text-brand-700" : isCompleted ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}`}>
            {pipelineStateLabel}
          </span>
        </div>
        <p className="mt-2 line-clamp-2 rounded-lg bg-slate-100 px-2 py-1 text-[11px] text-slate-700">
          {currentFile || "No active file"}
        </p>
        <div className="mt-3 space-y-3">
          {STAGES.map((stage, idx) => {
            const done = idx < stageIdx || (isCompleted && idx <= stageIdx);
            const activeStage = idx === stageIdx && isRunning;
            const stageState = done ? "done" : activeStage ? "active" : "pending";
            return (
              <div key={stage} className={`relative flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[11px] ${done ? "border-emerald-200 bg-emerald-50 text-emerald-800" : activeStage ? "border-brand-200 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600"}`}>
                {idx < STAGES.length - 1 && (
                  <div aria-hidden="true" className="absolute -bottom-5 left-5 flex h-4 w-3 flex-col items-center">
                    <span className={`h-3 w-px ${done || activeStage ? "bg-emerald-300" : "bg-slate-300"}`} />
                    <span className={`text-[9px] leading-none ${done || activeStage ? "text-emerald-400" : "text-slate-400"}`}>v</span>
                  </div>
                )}
                <StageIcon state={stageState} stage={stage} />
                <span className="flex-1 font-medium">{stage}</span>
                <span
                  className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                    done
                      ? "bg-emerald-100 text-emerald-700"
                      : activeStage
                        ? "bg-brand-100 text-brand-700"
                        : "bg-slate-100 text-slate-500"
                  }`}
                  title={done ? "Completed" : activeStage ? "Running" : "Pending"}
                >
                  {done ? "OK" : activeStage ? "..." : "-"}
                </span>
              </div>
            );
          })}
        </div>
      </section>
    </aside>
  );
}
