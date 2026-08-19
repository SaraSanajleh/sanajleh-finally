import { buildPackagePayload } from "@/lib/buildPackagePayload";
import type { WizardData, WizardMode } from "@/types/wizard";

/**
 * Call backend directly — NOT through Next.js proxy.
 * Prefer 127.0.0.1: on Windows, localhost often hits ::1 while Alpha is IPv4-only.
 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

const API_PREFIX = `${API_BASE}/api/v1`;

/** How often to poll async generation jobs (ms). */
const JOB_POLL_MS = 4000;
/** Max wait for a local GPU job (ms) — ~90 minutes. */
const JOB_MAX_WAIT_MS = 5_400_000;

export type BrainStatus = {
  api: "ok" | "down";
  llm: "ok" | "degraded" | "down";
  model?: string;
  provider?: string;
};

export type PackageJobStatus = {
  jobId: string;
  status: "queued" | "running" | "succeeded" | "failed" | string;
  error?: string | null;
  result?: unknown;
  elapsedSec?: number;
  stage?: string;
  stageLabel?: string;
};

export type GenerationProgressInfo = {
  stage?: string;
  stageLabel?: string;
  elapsedSec?: number;
};

async function readJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new Error(
      text.startsWith("Internal")
        ? "Backend timeout or crash — ensure backend runs on port 8000 and wait for LLM"
        : text.slice(0, 300),
    );
  }
}

function errorMessage(result: unknown, fallback: string): string {
  if (typeof result === "object" && result !== null && "error" in result) {
    const error = (result as { error?: { message?: string; details?: string[] } }).error;
    const details = Array.isArray(error?.details) ? error.details.join("; ") : "";
    return [error?.message, details].filter(Boolean).join(" — ") || fallback;
  }
  if (typeof result === "object" && result !== null && "detail" in result) {
    const detail = (result as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return fallback;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function checkBrainHealth(): Promise<BrainStatus> {
  try {
    const healthRes = await fetch(`${API_PREFIX}/health`, {
      signal: AbortSignal.timeout(10_000),
    });
    const health = (await readJsonResponse(healthRes)) as { status?: string };

    if (!healthRes.ok || health.status !== "ok") {
      return { api: "down", llm: "down" };
    }

    const llmRes = await fetch(`${API_PREFIX}/health/llm`, {
      signal: AbortSignal.timeout(15_000),
    });
    const llm = (await readJsonResponse(llmRes)) as {
      reachable?: boolean;
      model?: string;
      provider?: string;
    };

    return {
      api: "ok",
      llm: llm.reachable ? "ok" : "degraded",
      model: llm.model,
      provider: llm.provider,
    };
  } catch {
    return { api: "down", llm: "down" };
  }
}

async function startAsyncJob(mode: WizardMode, data: WizardData): Promise<string> {
  const payload = buildPackagePayload(mode, data);

  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}/packages/generate/async`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(60_000),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `Cannot reach backend at ${API_BASE}. Ensure Alpha is on :8000 (uvicorn) and retry. (${message})`,
    );
  }

  const result = (await readJsonResponse(response)) as {
    jobId?: string;
    success?: boolean;
  };

  if (!response.ok || !result?.jobId) {
    throw new Error(errorMessage(result, "Failed to start package generation job"));
  }

  return result.jobId;
}

async function pollJob(
  jobId: string,
  onProgress?: (info: GenerationProgressInfo) => void,
): Promise<unknown> {
  const started = Date.now();

  while (Date.now() - started < JOB_MAX_WAIT_MS) {
    let response: Response;
    try {
      response = await fetch(`${API_PREFIX}/packages/jobs/${jobId}`, {
        signal: AbortSignal.timeout(20_000),
      });
    } catch (error) {
      // Transient network blip — keep polling.
      const message = error instanceof Error ? error.message : String(error);
      console.warn("Job poll failed, retrying:", message);
      await sleep(JOB_POLL_MS);
      continue;
    }

    const body = (await readJsonResponse(response)) as PackageJobStatus & {
      success?: boolean;
    };

    if (!response.ok) {
      const message = errorMessage(body, `Job poll failed (${response.status})`);
      if (response.status === 404) {
        throw new Error(
          "The Brain restarted during generation. Click Generate My Package again.",
        );
      }
      throw new Error(message);
    }

    onProgress?.({
      stage: body.stage,
      stageLabel: body.stageLabel,
      elapsedSec: body.elapsedSec,
    });

    if (body.status === "succeeded") {
      return body.result ?? body;
    }

    if (body.status === "failed") {
      throw new Error(body.error || "Package generation failed");
    }

    await sleep(JOB_POLL_MS);
  }

  throw new Error(
    "Generation timed out while polling. Keep Ollama + Alpha running and retry with a shorter trip (2 days).",
  );
}

/**
 * Start async generation and poll until the package is ready.
 * Avoids long-lived browser fetch (which drops as "Failed to fetch" on slow local GPUs).
 */
export async function generatePackage(
  mode: WizardMode,
  data: WizardData,
  onProgress?: (info: GenerationProgressInfo) => void,
) {
  const jobId = await startAsyncJob(mode, data);
  return pollJob(jobId, onProgress);
}

export type EvaluationCaseSummary = {
  caseId?: string;
  createdAt?: string;
  trip_title?: string | null;
  rag?: {
    status?: string;
    cluster_count?: number;
    clusters?: Array<{ theme?: string }>;
  };
};

export type EvaluationCaseDetail = {
  caseId: string;
  manifest?: EvaluationCaseSummary & { trip_title?: string | null };
  input?: unknown;
  knowledge?: unknown;
  knowledge_preview?: {
    status?: string;
    source?: string | null;
    duration_days?: number | null;
    cluster_count?: number;
    clusters?: Array<{
      cluster_id?: number | null;
      theme?: string;
      poi_count?: number;
      hotel_count?: number;
      event_count?: number;
      poi_names?: string[];
      hotel_names?: string[];
      sample_restaurants?: string[];
      event_names?: string[];
    }>;
  };
  output?: unknown;
};

export async function fetchCases(): Promise<EvaluationCaseSummary[]> {
  const response = await fetch(`${API_PREFIX}/cases`, {
    signal: AbortSignal.timeout(20_000),
  });
  const body = (await readJsonResponse(response)) as {
    cases?: EvaluationCaseSummary[];
  };
  if (!response.ok) {
    throw new Error(errorMessage(body, "Failed to list cases"));
  }
  return body.cases ?? [];
}

export async function fetchCase(caseId: string): Promise<EvaluationCaseDetail> {
  const response = await fetch(`${API_PREFIX}/cases/${encodeURIComponent(caseId)}`, {
    signal: AbortSignal.timeout(30_000),
  });
  const body = (await readJsonResponse(response)) as EvaluationCaseDetail & {
    success?: boolean;
  };
  if (!response.ok) {
    throw new Error(errorMessage(body, `Failed to load case ${caseId}`));
  }
  return body;
}
