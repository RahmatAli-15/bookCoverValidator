import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { getAnnotationImageUrl, getCoverResults, validateCover } from "../services/coverApi";

function severityClass(level) {
  if (level === "CRITICAL") return "bg-red-900 text-white";
  if (level === "HIGH") return "bg-red-100 text-red-700";
  if (level === "MEDIUM") return "bg-amber-100 text-amber-700";
  return "bg-sky-100 text-sky-700";
}

export default function ResultsPage() {
  const location = useLocation();
  const stateJobId = location.state?.jobId;
  const [result, setResult] = useState(null);
  const [validation, setValidation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState("");

  const loadResults = async (jobId) => {
    if (!jobId) return;
    setLoading(true);
    setError("");
    try {
      const payload = await getCoverResults(jobId);
      setResult(payload);
      return payload;
    } catch (err) {
      setError(err.message || "Failed to fetch OCR results.");
      setResult(null);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const runValidation = async (jobIdArg) => {
    const jobId = jobIdArg || result?.job_id;
    if (!jobId) return;
    setIsValidating(true);
    setError("");
    try {
      const payload = await validateCover(jobId);
      setValidation(payload);
    } catch (err) {
      setError(err.message || "Validation failed.");
      setValidation(null);
    } finally {
      setIsValidating(false);
    }
  };

  useEffect(() => {
    if (!stateJobId) return;
    let active = true;
    const bootstrap = async () => {
      const ocr = await loadResults(stateJobId);
      if (active && ocr) await runValidation(stateJobId);
    };
    bootstrap();
    return () => {
      active = false;
    };
  }, [stateJobId]);

  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-2">
        <h2 className="text-2xl font-bold text-slate-900">Validation Results</h2>
        <p className="text-slate-600">Publishing QA output for annotated overlaps, compliance, and readiness decisions.</p>
      </header>

      {!!stateJobId && (
        <div className="flex items-center justify-end">
          <button type="button" onClick={() => runValidation(stateJobId)} disabled={isValidating || loading} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {isValidating ? "Running QA..." : "Re-run QA"}
          </button>
        </div>
      )}
      {!!error && <p className="text-sm font-medium text-red-600">{error}</p>}

      {validation && (
        <div className="grid gap-6 lg:grid-cols-2">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-base font-semibold text-slate-900">Executive QA Summary</h3>
            <p className="mt-2 text-sm text-slate-700">{validation.executive_summary || "Summary unavailable."}</p>
            <p className="mt-2 text-sm"><span className="font-semibold text-slate-900">Readiness Decision:</span> <span className="text-slate-700">{validation.publishing_decision || "Requires Manual Review"}</span></p>

            <h4 className="mt-5 text-sm font-semibold text-slate-900">Safe Zone Compliance</h4>
            <div className="mt-2 space-y-2">
              {(validation.safe_zone_compliance || []).map((item, idx) => (
                <div key={`${item.rule}-${idx}`} className="rounded-lg border border-slate-200 p-2 text-sm">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-slate-900">{item.rule}</p>
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${item.passed ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{item.passed ? "PASS" : "FAIL"}</span>
                  </div>
                  <p className="mt-1 text-slate-600">{item.message}</p>
                </div>
              ))}
            </div>

            <h4 className="mt-5 text-sm font-semibold text-slate-900">Operational Guidance</h4>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {(validation.operational_guidance || []).map((line, idx) => <li key={idx}>- {line}</li>)}
            </ul>

            <h4 className="mt-5 text-sm font-semibold text-slate-900">Correction Recommendation</h4>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {(validation.correction_recommendations || []).map((line, idx) => <li key={idx}>- {line}</li>)}
            </ul>

            <h4 className="mt-5 text-sm font-semibold text-slate-900">Issue Severity Cards</h4>
            <div className="mt-2 space-y-2">
              {validation.issues.length === 0 && <p className="text-sm text-slate-600">No issues detected.</p>}
              {validation.issues.map((issue, idx) => (
                <div key={`${issue.type}-${idx}`} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{issue.type}</p>
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${severityClass(issue.severity)}`}>{issue.severity}</span>
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{issue.message}</p>
                  <p className="mt-1 text-xs text-slate-500">Text: {issue.text || "(empty)"}</p>
                  <p className="mt-1 text-xs text-slate-500">Heatmap overlap: {issue.overlap_percentage}%</p>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-base font-semibold text-slate-900">Annotated Preview and Overlap Heatmap</h3>
            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <img src={getAnnotationImageUrl(validation.job_id)} alt="Annotated cover validation preview" className="max-h-[560px] w-full rounded object-contain" />
            </div>
            <p className="mt-2 text-xs text-slate-500">Stored at: {validation.annotated_image_path}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              <span className="rounded bg-yellow-100 px-2 py-0.5 text-yellow-800">LOW</span>
              <span className="rounded bg-orange-100 px-2 py-0.5 text-orange-800">MEDIUM</span>
              <span className="rounded bg-red-100 px-2 py-0.5 text-red-700">HIGH</span>
              <span className="rounded bg-red-900 px-2 py-0.5 text-white">CRITICAL</span>
            </div>
          </article>
        </div>
      )}
    </section>
  );
}
