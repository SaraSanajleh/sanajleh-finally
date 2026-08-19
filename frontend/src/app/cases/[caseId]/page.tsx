"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { fetchCase, type EvaluationCaseDetail } from "@/lib/api";

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = typeof params.caseId === "string" ? params.caseId : "";
  const [data, setData] = useState<EvaluationCaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"preview" | "full" | "input" | "output">("preview");

  useEffect(() => {
    if (!caseId) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const detail = await fetchCase(caseId);
        if (!cancelled) {
          setData(detail);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load case");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const preview = data?.knowledge_preview;
  const payload =
    tab === "preview"
      ? preview
      : tab === "full"
        ? data?.knowledge
        : tab === "input"
          ? data?.input
          : data?.output;

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 20px" }}>
      <p style={{ marginBottom: 12 }}>
        <Link href="/cases">← All cases</Link>
        {" · "}
        <Link href="/wizard">Wizard</Link>
      </p>
      <h1 style={{ marginBottom: 8 }}>{data?.manifest?.trip_title || caseId}</h1>
      <p style={{ color: "#6b7280", marginBottom: 20 }}>
        Case ID: <code>{caseId}</code>
        {data?.manifest?.createdAt ? ` · ${data.manifest.createdAt}` : ""}
      </p>

      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      {!error && !data && <p>Loading…</p>}

      {data && (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
            {(
              [
                ["preview", "RAG preview"],
                ["full", "Full knowledge JSON"],
                ["input", "Input"],
                ["output", "Package output"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`btn btn-sm ${tab === key ? "btn-success" : "btn-outline-secondary"}`}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "preview" && preview && (
            <div style={{ marginBottom: 16 }}>
              <p>
                Status: <strong>{preview.status}</strong>
                {preview.source ? ` · ${preview.source}` : ""} · clusters{" "}
                {preview.cluster_count ?? 0} · days {preview.duration_days ?? "-"}
              </p>
              {(preview.clusters ?? []).map((cluster, index) => (
                <section
                  key={`${cluster.cluster_id ?? index}`}
                  style={{
                    border: "1px solid #e5e7eb",
                    borderRadius: 8,
                    padding: 14,
                    marginBottom: 12,
                    background: "#fff",
                  }}
                >
                  <h2 style={{ fontSize: 18, marginBottom: 8 }}>
                    {cluster.theme || `Cluster ${cluster.cluster_id ?? index}`}
                  </h2>
                  <p style={{ color: "#4b5563" }}>
                    POIs {cluster.poi_count ?? 0} · Hotels {cluster.hotel_count ?? 0} · Events{" "}
                    {cluster.event_count ?? 0}
                  </p>
                  {(cluster.poi_names ?? []).length > 0 && (
                    <p>
                      <strong>POIs:</strong> {(cluster.poi_names ?? []).join(" · ")}
                    </p>
                  )}
                  {(cluster.hotel_names ?? []).length > 0 && (
                    <p>
                      <strong>Hotels:</strong> {(cluster.hotel_names ?? []).join(" · ")}
                    </p>
                  )}
                  {(cluster.sample_restaurants ?? []).length > 0 && (
                    <p>
                      <strong>Restaurants:</strong>{" "}
                      {(cluster.sample_restaurants ?? []).join(" · ")}
                    </p>
                  )}
                  {(cluster.event_names ?? []).length > 0 && (
                    <p>
                      <strong>Events:</strong> {(cluster.event_names ?? []).join(" · ")}
                    </p>
                  )}
                </section>
              ))}
            </div>
          )}

          <pre
            style={{
              background: "#0f172a",
              color: "#e2e8f0",
              padding: 16,
              borderRadius: 8,
              overflow: "auto",
              maxHeight: "70vh",
              fontSize: 12,
            }}
          >
            {JSON.stringify(payload, null, 2)}
          </pre>
        </>
      )}
    </main>
  );
}
