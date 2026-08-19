export type WizardMode = "ready_packages" | "ai_builder";

/* ---------------------------------------------------------------------- */
/*  Option id unions (mirror the constants that will live in constants/)  */
/* ---------------------------------------------------------------------- */

export type GroupTypeId = "solo" | "couple" | "family" | "friends" | "business";

export type AccommodationTypeId =
  | "no_pref"
  | "hotel"
  | "resort"
  | "boutique"
  | "eco_lodge"
  | "desert_camp";

export type PriorityId =
  | "budget"
  | "famous"
  | "hidden"
  | "authentic"
  | "sustainable"
  | "comfort"
  | "maximize"
  | "family";

export type DurationOption = "1" | "2" | "3" | "5" | "7" | "Custom";

export type AirportId = "AMM" | "AQJ" | "OTHER";

/* ---------------------------------------------------------------------- */
/*  Wizard form state                                                     */
/* ---------------------------------------------------------------------- */

export interface WizardData {
  // Step 1 — Trip Basics
  startDate: string;
  duration: DurationOption;
  customDuration: string;
  arrivalAirport: AirportId | "";
  arrivalTime: string;
  totalBudget: string;
  preferredLanguage: string;
  preferredRegion: string[];

  // Step 2 — Travelers
  adults: number;
  children: number;
  childrenAges: string[];
  seniors: number;
  groupType: GroupTypeId | "";
  accessibilityNeeds: string[];

  // Step 3 — Journey Type
  interests: string[];
  tripPace: string;
  activityLevel: string;
  mustVisit: string[];

  // Step 4 — Customize
  placesToAvoid: string;
  accommodationType: AccommodationTypeId | "";
  hotelRating: string;
  cuisine: string[];
  specialOccasion: string;
  smePreferences: string[];

  // Step 5 — AI Priorities
  aiPriority: PriorityId | "";

  // Step 6 — Tell AI
  freeText: string;
}

/** The full state carried by the wizard, including how the user got here. */
export interface WizardState {
  mode: WizardMode;
  step: number;
  data: WizardData;
}

/* ---------------------------------------------------------------------- */
/*  Derived / UI-only values (not submitted, just displayed)              */
/* ---------------------------------------------------------------------- */

export interface WizardMatchIndicators {
  hotelsMatch: number;
  poisMatch: number;
  eventsMatch: number;
  smesMatch: number;
  restaurantsMatch: number;
  confidence: number;
}


export interface WizardSubmissionPayload {
  requestType: WizardMode;
  submittedAt: string; // ISO timestamp

  trip: {
    startDate: string;
    endDate: string;
    durationDays: number;
    arrivalAirport: AirportId | "";
    arrivalTime?: string;
    totalBudget: number | null;
    preferredLanguage: string;
    preferredRegions: string[];
  };

  travelers: {
    adults: number;
    children: number;
    childrenAges: number[];
    seniors: number;
    groupType: GroupTypeId | "";
    accessibilityNeeds: string[];
  };

  preferences: {
    interests: string[];
    tripPace: string;
    activityLevel: string;
    mustVisit: string[];
    placesToAvoid: string;
    accommodationType: AccommodationTypeId | "";
    hotelRating: string;
    cuisine: string[];
    specialOccasion: string;
    smePreferences: string[];
    aiPriority: PriorityId | "";
  };

  freeText: string;
}