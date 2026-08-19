export type GeoPoint = {
  latitude?: number | null;
  longitude?: number | null;
  precision?: string;
};

export type SourceRef = {
  dataset: string;
  record_id: string;
};

export type ScheduleItem = {
  time?: string;
  end_time?: string;
  slot?: string;
  type?: string;
  item_id?: string;
  name?: string;
  duration_minutes?: number | null;
  location?: string;
  coordinates?: GeoPoint | null;
  description?: string;
  reason?: string;
  matched_preferences?: string[];
  estimated_cost?: string;
  source?: SourceRef | null;
  confidence?: string;
};

export type SMESpec = {
  label: string;
  value: string;
};

export type DaySME = {
  sme_id: string;
  sme_type: string;
  name: string;
  role?: string;
  location?: string;
  experience_type?: string;
  match_score?: number;
  reason?: string;
  matched_because?: string[];
  known_for?: string[];
  specializations?: string[];
  languages?: string[];
  experience_years?: number | null;
  destinations_covered?: string[];
  covers_regions?: string[];
  package_role?: string;
  specs?: SMESpec[];
  source?: SourceRef | null;
  coordinates?: GeoPoint | null;
};

export type DayPlan = {
  day: number;
  date?: string;
  region?: string;
  theme?: string;
  summary?: string;
  is_arrival_day?: boolean;
  schedule?: ScheduleItem[];
  smes?: DaySME[];
  transport_notes?: string;
};

export type TourismPackage = {
  package_id?: string;
  status?: string;
  welcome_message?: string;
  trip_title?: string;
  trip?: {
    title?: string;
    summary?: string;
    start_date?: string;
    end_date?: string;
    duration_days?: number;
    nights?: number;
    regions?: string[];
    arrival_airport?: string;
    language?: string;
  };
  traveler_profile?: {
    group_type?: string;
    adults?: number;
    children?: number;
    seniors?: number;
    total_travelers?: number;
    interests?: string[];
    pace?: string;
    activity_level?: string;
    accessibility_needs?: string[];
  };
  planning?: {
    strategy?: string;
    constraint_status?: {
      status?: string;
      unmet?: Array<{ item?: string; reason?: string; reason_code?: string }>;
    };
    assumptions?: string[];
    weather_status?: string;
    decisions?: Array<{ code?: string; title?: string; why?: string; effect?: string }>;
  };
  days?: DayPlan[];
  budget?: {
    currency?: string;
    traveler_budget?: number | null;
    estimated_total?: string;
    band?: string;
    items?: Array<{ category?: string; estimated_cost?: string; notes?: string }>;
    disclaimer?: string;
  };
  sme_value?: {
    headline?: string;
    summary?: string;
    recommended?: DaySME[];
  };
  warnings?: Array<{ code?: string; message?: string; severity?: string }>;
  explanations?: {
    trip_planning_reason?: string;
    highlights?: string[];
    why_smes?: string[];
    context_benefits?: string[];
  };
};

export type PackageGenerationResult = {
  success?: boolean;
  package?: TourismPackage;
  metadata?: {
    model?: string;
    provider?: string;
    caseId?: string;
    latencyMs?: number;
    rag?: {
      status?: string;
      cluster_count?: number;
      clusters?: Array<{ theme?: string; poi_names?: string[] }>;
    };
    trace?: {
      stages?: string[];
      knowledge_counts?: Record<string, number>;
      sme_counts?: Record<string, number>;
    };
  };
  knowledge?: unknown;
};

export function unwrapPackage(result: unknown): TourismPackage | null {
  if (!result || typeof result !== "object") {
    return null;
  }
  const body = result as PackageGenerationResult & TourismPackage;
  if (body.package && typeof body.package === "object") {
    return body.package;
  }
  if (Array.isArray(body.days) || body.trip_title || body.trip) {
    return body as TourismPackage;
  }
  return null;
}
