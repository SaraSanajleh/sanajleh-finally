"use client";

import { useMemo, useState } from "react";

import styles from "@/styles/wizard/wizard.module.css";

export type RagClusterPreview = {
  cluster_id?: number | null;
  theme?: string;
  poi_count?: number;
  hotel_count?: number;
  event_count?: number;
  poi_names?: string[];
  hotel_names?: string[];
  sample_restaurants?: string[];
  event_names?: string[];
};

export type RagEvaluationSummary = {
  status?: string;
  source?: string | null;
  duration_days?: number | null;
  cluster_count?: number;
  clusters?: RagClusterPreview[];
};

type PackageResultShape = {
  metadata?: {
    caseId?: string | null;
    rag?: RagEvaluationSummary | null;
  };
  knowledge?: unknown;
};

type Props = {
  result: unknown;
};

function asResult(value: unknown): PackageResultShape | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  return value as PackageResultShape;
}

export default function RagKnowledgePanel({ result }: Props) {
  const parsed = useMemo(() => asResult(result), [result]);
  const rag = parsed?.metadata?.rag ?? null;
  const caseId = parsed?.metadata?.caseId ?? null;
  const knowledge = parsed?.knowledge ?? null;
  const [showFull, setShowFull] = useState(false);

  if (!rag && !knowledge && !caseId) {
    return null;
  }

  return (
    <div className={styles.jsonPanel}>
      <h5>RAG Knowledge (for evaluation)</h5>
      <p style={{ marginBottom: 12, color: "#4b5563" }}>
        {caseId ? (
          <>
            Case ID: <code>{caseId}</code>
            {" · "}
            <a href={`/cases/${encodeURIComponent(caseId)}`}>Open case page</a>
            {" · "}
            <a href="/cases">All cases</a>
          </>
        ) : (
          <a href="/cases">Browse saved cases</a>
        )}
      </p>

      {rag ? (
        <div className={styles.summaryBox} style={{ marginBottom: 16 }}>
          <p>
            <strong>Status:</strong> {rag.status ?? "unknown"}
            {rag.source ? ` · source=${rag.source}` : ""}
          </p>
          <p>
            <strong>Duration days:</strong> {rag.duration_days ?? "-"}
            {" · "}
            <strong>Clusters:</strong> {rag.cluster_count ?? 0}
          </p>

          {(rag.clusters ?? []).map((cluster, index) => (
            <div key={`${cluster.cluster_id ?? index}-${cluster.theme ?? ""}`} style={{ marginTop: 14 }}>
              <h5 style={{ marginBottom: 6 }}>
                Cluster {cluster.cluster_id ?? index}: {cluster.theme || "—"}
              </h5>
              <p>
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
                  <strong>Restaurants:</strong> {(cluster.sample_restaurants ?? []).join(" · ")}
                </p>
              )}
              {(cluster.event_names ?? []).length > 0 && (
                <p>
                  <strong>Events:</strong> {(cluster.event_names ?? []).join(" · ")}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {knowledge ? (
        <>
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm"
            onClick={() => setShowFull((v) => !v)}
            style={{ marginBottom: 10 }}
          >
            {showFull ? "Hide full knowledge JSON" : "Show full knowledge JSON"}
          </button>
          {showFull ? (
            <pre className={styles.jsonOutput}>{JSON.stringify(knowledge, null, 2)}</pre>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
