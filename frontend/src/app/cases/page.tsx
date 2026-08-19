"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchCases, type EvaluationCaseSummary } from "@/lib/api";

export default function CasesPage() {
  const [cases, setCases] = useState<EvaluationCaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fetchCases();
        if (!cancelled) {
          setCases(list);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load cases");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "32px 20px" }}>
      <h1 style={{ marginBottom: 8 }}>RAG evaluation cases</h1>
      <p style={{ color: "#4b5563", marginBottom: 24 }}>
        Each package generation saves input + full Retriever knowledge + package output.
        Open a case to review what RAG returned.
      </p>
      <p style={{ marginBottom: 20 }}>
        <Link href="/wizard">← Back to wizard</Link>
      </p>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      {!loading && !error && cases.length === 0 && (
        <p>No cases yet. Generate a package from the wizard first.</p>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {cases.map((item) => {
          const caseId = item.caseId ?? "";
          const rag = item.rag;
          return (
            <li
              key={caseId}
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 16,
                marginBottom: 12,
                background: "#fff",
              }}
            >
              <Link href={`/cases/${encodeURIComponent(caseId)}`} style={{ fontWeight: 600 }}>
                {item.trip_title || caseId}
              </Link>
              <div style={{ color: "#6b7280", fontSize: 14, marginTop: 6 }}>
                {item.createdAt ?? ""}
                {rag?.status ? ` · RAG ${rag.status}` : ""}
                {typeof rag?.cluster_count === "number"
                  ? ` · ${rag.cluster_count} clusters`
                  : ""}
              </div>
              {(rag?.clusters ?? []).length > 0 && (
                <div style={{ fontSize: 14, marginTop: 8, color: "#374151" }}>
                  {(rag?.clusters ?? []).map((c) => c.theme).filter(Boolean).join(" · ")}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </main>
  );
}
