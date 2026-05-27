import { useEffect, useState } from "react";

import { getReviewQueue } from "../services/coverApi";

export default function ReviewDashboardPage() {
  const [filter, setFilter] = useState("");
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadQueue = async (statusFilter = filter) => {
    setLoading(true);
    setError("");
    try {
      const payload = await getReviewQueue(statusFilter || undefined);
      setQueue(payload.items || []);
    } catch (err) {
      setError(err.message || "Failed to load review queue.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Ops Review Queue</h2>
          <p className="text-slate-600">Open any publishing cover job to inspect full validation results.</p>
        </div>
        <div className="flex gap-2">
          <button className={`rounded-lg px-3 py-2 text-sm font-semibold ${filter === "" ? "bg-slate-900 text-white" : "border border-slate-300 bg-white text-slate-700"}`} onClick={() => { setFilter(""); loadQueue(""); }}>All</button>
          <button className={`rounded-lg px-3 py-2 text-sm font-semibold ${filter === "PASS" ? "bg-emerald-600 text-white" : "border border-slate-300 bg-white text-slate-700"}`} onClick={() => { setFilter("PASS"); loadQueue("PASS"); }}>PASS</button>
          <button className={`rounded-lg px-3 py-2 text-sm font-semibold ${filter === "REVIEW_NEEDED" ? "bg-amber-600 text-white" : "border border-slate-300 bg-white text-slate-700"}`} onClick={() => { setFilter("REVIEW_NEEDED"); loadQueue("REVIEW_NEEDED"); }}>REVIEW_NEEDED</button>
        </div>
      </header>

      <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        {loading && <p className="text-sm text-slate-500">Loading queue...</p>}
        {!loading && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2">Job ID</th>
                  <th>Filename</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Issue Count</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((item) => (
                  <tr
                    key={item.job_id}
                    className="border-t border-slate-100"
                  >
                    <td className="py-2 font-semibold text-slate-800">#{item.job_id}</td>
                    <td className="text-slate-700">{item.file_name}</td>
                    <td>{item.validation_status}</td>
                    <td>{item.overall_confidence}</td>
                    <td>{item.issue_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>

      {!!error && <p className="text-sm font-medium text-red-600">{error}</p>}
    </section>
  );
}
