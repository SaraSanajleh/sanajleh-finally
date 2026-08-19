const API_BASE = window.location.origin + "/api/v1";

const REGIONS = [
  "Amman", "Petra", "Wadi Rum", "Aqaba", "Dead Sea",
  "Jerash", "Ajloun", "Madaba", "Irbid",
];

const INTERESTS = [
  "history", "nature", "food", "culture", "adventure",
  "shopping", "photography", "desert", "beaches", "art",
  "wellness", "hiking", "camping", "local_experiences",
  "festivals", "archaeology", "religious_sites", "cycling",
  "scenic_views", "luxury", "local_events", "eco_tourism",
  "wildlife", "museums",
];

const MUST_VISIT = [
  "Petra", "Wadi Rum", "Dead Sea", "Jerash",
  "Ajloun", "Aqaba", "Amman", "Madaba",
];

const ACCESSIBILITY = [
  "Wheelchair Access", "Limited Walking", "Visual Assistance",
  "Hearing Assistance", "Elder Friendly",
];

const CUISINE = [
  "Local Jordanian", "Middle Eastern", "International",
  "Vegetarian", "Vegan", "Halal", "Seafood",
  "Fine Dining", "Street Food",
];

const SME_PREFS = [
  "Family-owned Businesses", "Eco-friendly SMEs", "Highly Rated SMEs",
  "Women-led Businesses", "Community-based Tourism", "Luxury Services",
];

function buildCheckboxes(containerId, values, defaultChecked = []) {
  const container = document.getElementById(containerId);
  values.forEach((value) => {
    const id = `${containerId}-${value.replace(/\s+/g, "-")}`;
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" name="${containerId}" value="${value}" id="${id}" ${defaultChecked.includes(value) ? "checked" : ""} /> ${value}`;
    container.appendChild(label);
  });
}

function getCheckedValues(name) {
  return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map((el) => el.value);
}

function parseChildrenAges(raw, count) {
  if (count === 0) return [];
  if (!raw.trim()) return Array(count).fill("");
  const parts = raw.split(",").map((s) => s.trim());
  while (parts.length < count) parts.push("");
  return parts.slice(0, count);
}

function buildPayload(form) {
  const data = new FormData(form);
  const children = parseInt(data.get("children"), 10);
  const childrenAges = parseChildrenAges(data.get("childrenAges") || "", children);

  return {
    mode: data.get("mode"),
    requestedAt: new Date().toISOString(),
    trip: {
      startDate: data.get("startDate"),
      duration: data.get("duration"),
      arrivalAirport: data.get("arrivalAirport"),
      totalBudget: parseFloat(data.get("totalBudget")),
      preferredLanguage: data.get("preferredLanguage"),
      preferredRegions: getCheckedValues("regions"),
    },
    travelers: {
      adults: parseInt(data.get("adults"), 10),
      children,
      childrenAges,
      seniors: parseInt(data.get("seniors"), 10),
      groupType: data.get("groupType"),
      accessibilityNeeds: getCheckedValues("accessibility"),
    },
    preferences: {
      interests: getCheckedValues("interests"),
      tripPace: data.get("tripPace"),
      activityLevel: data.get("activityLevel"),
      mustVisit: getCheckedValues("mustVisit"),
      placesToAvoid: data.get("placesToAvoid") || "",
    },
    accommodation: {
      type: data.get("accommodationType") || "",
      rating: data.get("accommodationRating") || "",
    },
    dining: {
      cuisine: getCheckedValues("cuisine"),
    },
    extras: {
      specialOccasion: data.get("specialOccasion") || "",
      smePreferences: getCheckedValues("smePreferences"),
      aiPriority: data.get("aiPriority") || "",
      freeText: data.get("freeText") || "",
    },
  };
}

function setDefaultDate() {
  const input = document.querySelector('input[name="startDate"]');
  const date = new Date();
  date.setMonth(date.getMonth() + 1);
  input.value = date.toISOString().split("T")[0];
}

document.addEventListener("DOMContentLoaded", () => {
  buildCheckboxes("regions", REGIONS, ["Petra", "Wadi Rum", "Dead Sea"]);
  buildCheckboxes("interests", INTERESTS, ["history", "photography", "hiking", "food"]);
  buildCheckboxes("mustVisit", MUST_VISIT, ["Petra", "Dead Sea"]);
  buildCheckboxes("accessibility", ACCESSIBILITY);
  buildCheckboxes("cuisine", CUISINE, ["Local Jordanian"]);
  buildCheckboxes("smePreferences", SME_PREFS);
  setDefaultDate();

  const form = document.getElementById("package-form");
  const submitBtn = document.getElementById("submit-btn");
  const statusEl = document.getElementById("status");
  const responseSection = document.getElementById("response-section");
  const responseViewer = document.getElementById("response-viewer");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitBtn.disabled = true;
    statusEl.textContent = "Generating package...";
    statusEl.className = "";
    responseSection.hidden = true;

    const payload = buildPayload(form);

    try {
      const response = await fetch(`${API_BASE}/packages/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      responseSection.hidden = false;
      responseViewer.textContent = JSON.stringify(result, null, 2);

      if (response.ok) {
        statusEl.textContent = `Done in ${result.metadata?.latencyMs ?? "?"}ms`;
        statusEl.className = "success";
      } else {
        statusEl.textContent = result.error?.message || "Request failed";
        statusEl.className = "error";
      }
    } catch (err) {
      responseSection.hidden = false;
      responseViewer.textContent = String(err);
      statusEl.textContent = "Network error — is the API running?";
      statusEl.className = "error";
    } finally {
      submitBtn.disabled = false;
    }
  });
});
