import type { WizardData, WizardMode } from "@/types/wizard";

const INTEREST_MAP: Record<string, string> = {
  History: "history",
  Culture: "culture",
  Nature: "nature",
  Adventure: "adventure",
  Food: "food",
  Photography: "photography",
  Shopping: "shopping",
  Museums: "museums",
  Camping: "camping",
  Hiking: "hiking",
  Luxury: "luxury",
  Wellness: "wellness",
  "Local Experiences": "local_experiences",
  "Religious Sites": "religious_sites",
};

const ACCESSIBILITY_MAP: Record<string, string> = {
  Wheelchair: "Wheelchair Access",
  "Limited Walking": "Limited Walking",
  Visual: "Visual Assistance",
  Hearing: "Hearing Assistance",
  "Elder Friendly": "Elder Friendly",
};

const TRIP_PACE_MAP: Record<string, string> = {
  Relaxed: "Relaxed",
  Balanced: "Balanced",
  Fast: "Fast-paced",
  "Fast-paced": "Fast-paced",
  "No Preference": "No Preference",
};

const HOTEL_RATING_MAP: Record<string, string> = {
  "3 Stars": "3 star",
  "4 Stars": "4 star",
  "5 Stars": "5 star",
  "No Preference": "No Preference",
};

const CUISINE_MAP: Record<string, string> = {
  Jordanian: "Local Jordanian",
  Arabic: "Middle Eastern",
  Italian: "International",
  Seafood: "Seafood",
  BBQ: "Middle Eastern",
  Vegetarian: "Vegetarian",
  Vegan: "Vegan",
  "Fast Food": "Street Food",
  Desserts: "International",
};

const SME_MAP: Record<string, string> = {
  "Family-owned": "Family-owned Businesses",
  "Eco-friendly": "Eco-friendly SMEs",
  "Women-led": "Women-led Businesses",
  "Community-based": "Community-based Tourism",
  Luxury: "Luxury Services",
};

function resolveDuration(data: WizardData): string {
  if (data.duration === "Custom") {
    return data.customDuration.trim() || "5";
  }
  return data.duration;
}

function mapMode(mode: WizardMode): "build" | "browse" {
  return mode === "ready_packages" ? "browse" : "build";
}

function defaultStartDate(): string {
  const date = new Date();
  date.setMonth(date.getMonth() + 1);
  return date.toISOString().split("T")[0];
}

function mapList<T extends string>(
  values: string[],
  dictionary: Record<string, T>,
): T[] {
  return values
    .map((value) => dictionary[value])
    .filter((value): value is T => Boolean(value));
}

export function buildPackagePayload(mode: WizardMode, data: WizardData) {
  const adults = data.adults > 0 ? data.adults : 1;
  const childrenAges = data.childrenAges
    .slice(0, data.children)
    .map((age) => age || "0");

  while (childrenAges.length < data.children) {
    childrenAges.push("0");
  }

  const interests = mapList(data.interests, INTEREST_MAP);
  const parsedBudget = Number.parseFloat(data.totalBudget);

  return {
    mode: mapMode(mode),
    requestedAt: new Date().toISOString(),
    trip: {
      startDate: data.startDate || defaultStartDate(),
      duration: resolveDuration(data),
      arrivalAirport: data.arrivalAirport || "AMM",
      arrivalTime: data.arrivalTime || "14:00",
      totalBudget: Number.isFinite(parsedBudget) ? parsedBudget : 1500,
      preferredLanguage: data.preferredLanguage || "English",
      preferredRegions: data.preferredRegion,
    },
    travelers: {
      adults,
      children: data.children,
      childrenAges,
      seniors: data.seniors,
      groupType: data.groupType || "solo",
      accessibilityNeeds: mapList(data.accessibilityNeeds, ACCESSIBILITY_MAP),
    },
    preferences: {
      interests: interests.length > 0 ? interests : ["culture"],
      tripPace: TRIP_PACE_MAP[data.tripPace] || "Balanced",
      activityLevel: data.activityLevel || "Moderate",
      mustVisit: data.mustVisit,
      placesToAvoid: data.placesToAvoid || "",
    },
    accommodation: {
      type: data.accommodationType || "",
      rating: HOTEL_RATING_MAP[data.hotelRating] || data.hotelRating || "",
    },
    dining: {
      cuisine: mapList(data.cuisine, CUISINE_MAP),
    },
    extras: {
      specialOccasion: data.specialOccasion || "None",
      smePreferences: mapList(data.smePreferences, SME_MAP),
      aiPriority: data.aiPriority || "",
      freeText: data.freeText || "",
    },
  };
}
