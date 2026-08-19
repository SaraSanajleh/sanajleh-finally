"use client";
import { useState, useEffect } from "react";
import {
  Calendar, MapPin, Plane, Wallet, Globe, Users, Baby, PersonStanding,
  Accessibility, Compass, Mountain, UtensilsCrossed, Palette, ShoppingBag,
  Camera, Sun, Waves, HeartPulse, Footprints, Tent, PartyPopper, Pickaxe,
  Church, Bike, Sunrise, Wine, Music, Sprout, Bird, BookOpen, ScrollText,
  Landmark, Building2, Star, ChefHat, Cake, Heart, Sparkles, MessageSquare,
  CheckCircle2, ChevronRight, ChevronLeft, Minus, Plus, Leaf, HandHeart,
} from "lucide-react";

/* ---------------------------------- data ---------------------------------- */

const REGIONS = ["Amman", "Petra", "Wadi Rum", "Aqaba", "Dead Sea", "Jerash", "Ajloun", "Madaba", "Irbid"];
const MUST_VISIT = ["Petra", "Wadi Rum", "Dead Sea", "Jerash", "Ajloun", "Aqaba", "Amman", "Madaba"];
const LANGUAGES = ["English", "Arabic", "French", "German", "Spanish", "Italian"];
const AIRPORTS = [
  { id: "AMM", label: "Queen Alia International (AMM)" },
  { id: "AQJ", label: "King Hussein Int'l, Aqaba (AQJ)" },
  { id: "OTHER", label: "Other" },
];
const DURATIONS = ["1", "2", "3", "5", "7", "Custom"];

const INTERESTS = [
  { id: "history", label: "History", Icon: ScrollText },
  { id: "nature", label: "Nature", Icon: Leaf },
  { id: "food", label: "Food", Icon: UtensilsCrossed },
  { id: "culture", label: "Culture", Icon: Landmark },
  { id: "adventure", label: "Adventure", Icon: Mountain },
  { id: "shopping", label: "Shopping", Icon: ShoppingBag },
  { id: "photography", label: "Photography", Icon: Camera },
  { id: "desert", label: "Desert", Icon: Sun },
  { id: "beaches", label: "Beaches", Icon: Waves },
  { id: "art", label: "Art", Icon: Palette },
  { id: "wellness", label: "Wellness", Icon: HeartPulse },
  { id: "hiking", label: "Hiking", Icon: Footprints },
  { id: "camping", label: "Camping", Icon: Tent },
  { id: "local_experiences", label: "Local Experiences", Icon: Users },
  { id: "festivals", label: "Festivals", Icon: PartyPopper },
  { id: "archaeology", label: "Archaeology", Icon: Pickaxe },
  { id: "religious_sites", label: "Religious Sites", Icon: Church },
  { id: "cycling", label: "Cycling", Icon: Bike },
  { id: "scenic_views", label: "Scenic Views", Icon: Sunrise },
  { id: "luxury", label: "Luxury Experiences", Icon: Wine },
  { id: "local_events", label: "Local Events", Icon: Music },
  { id: "eco_tourism", label: "Eco Tourism", Icon: Sprout },
  { id: "wildlife", label: "Wildlife", Icon: Bird },
  { id: "museums", label: "Museums", Icon: BookOpen },
];

const GROUP_TYPES = [
  { id: "solo", label: "Solo", Icon: PersonStanding },
  { id: "couple", label: "Couple", Icon: Heart },
  { id: "family", label: "Family", Icon: Users },
  { id: "friends", label: "Friends", Icon: Users },
  { id: "business", label: "Business", Icon: Building2 },
];

const ACCESS_NEEDS = ["Wheelchair Access", "Limited Walking", "Visual Assistance", "Hearing Assistance", "Elder Friendly"];
const TRIP_PACE = ["Relaxed", "Balanced", "Fast-paced", "No Preference"];
const ACTIVITY_LEVEL = ["Easy", "Moderate", "Active", "No Preference"];

const ACCOMMODATION = [
  { id: "no_pref", label: "No Preference", Icon: Compass },
  { id: "hotel", label: "Hotel", Icon: Building2 },
  { id: "resort", label: "Resort", Icon: Sun },
  { id: "boutique", label: "Boutique Hotel", Icon: Star },
  { id: "eco_lodge", label: "Eco Lodge", Icon: Sprout },
  { id: "desert_camp", label: "Desert Camp", Icon: Tent },
];
const HOTEL_RATING = ["No Preference", "3 star", "4 star", "5 star"];
const CUISINE = ["Local Jordanian", "Middle Eastern", "International", "Vegetarian", "Vegan", "Halal", "Seafood", "Fine Dining", "Street Food"];
const OCCASIONS = ["None", "Birthday", "Honeymoon", "Anniversary", "Graduation", "Family Celebration"];
const SME = ["Family-owned Businesses", "Eco-friendly SMEs", "Highly Rated SMEs", "Women-led Businesses", "Community-based Tourism", "Luxury Services"];

const PRIORITIES = [
  { id: "budget", label: "Stay within my budget", desc: "Cost control comes first, even if it means fewer extras." },
  { id: "famous", label: "Visit famous attractions", desc: "Prioritize the landmarks Jordan is best known for." },
  { id: "hidden", label: "Discover hidden gems", desc: "Favor lesser-known spots over crowded highlights." },
  { id: "authentic", label: "Authentic local experiences", desc: "Real life over polished tourist experiences." },
  { id: "sustainable", label: "Sustainable tourism", desc: "Favor eco-conscious and low-impact choices." },
  { id: "comfort", label: "Comfort & relaxation", desc: "Minimize effort, maximize ease at every step." },
  { id: "maximize", label: "Maximize experiences", desc: "Pack in as much as the days allow." },
  { id: "family", label: "Family-friendly planning", desc: "Every choice filtered for the whole family." },
];

const STEPS = [
  { id: 1, label: "Trip Basics", Icon: Calendar },
  { id: 2, label: "Travelers", Icon: Users },
  { id: 3, label: "Journey Type", Icon: Compass },
  { id: 4, label: "Customize", Icon: Sparkles },
  { id: 5, label: "AI Priorities", Icon: Heart },
  { id: 6, label: "Tell AI", Icon: MessageSquare },
  { id: 7, label: "Review & Build", Icon: CheckCircle2 },
];

const NO_PREF = "No Preference";

/* -------------------------------- helpers --------------------------------- */

function addDays(dateStr, days) {
  if (!dateStr || !days) return "";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  d.setDate(d.getDate() + Number(days));
  return d.toISOString().slice(0, 10);
}

/* ------------------------------ ui primitives ------------------------------ */

function Label({ children, required }) {
  return (
    <label className="block text-sm font-medium text-gray-700 mb-2">
      {children}
      {required && <span className="text-emerald-600 ml-0.5">*</span>}
    </label>
  );
}

function SectionTitle({ icon: Icon, title, sub }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-700 shrink-0">
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <h3 className="font-semibold text-gray-900">{title}</h3>
        {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function Chip({ active, onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3.5 py-1.5 rounded-full text-sm border transition-colors ${
        active
          ? "bg-emerald-600 border-emerald-600 text-white"
          : "bg-white border-gray-300 text-gray-700 hover:border-emerald-400"
      }`}
    >
      {label}
    </button>
  );
}

function OptionCard({ active, onClick, label, sub, icon: Icon, compact }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative text-left rounded-xl border-2 transition-all ${
        compact ? "flex flex-col items-center text-center gap-2 p-3" : "flex items-center gap-3 p-4"
      } ${
        active
          ? "border-emerald-600 bg-emerald-50"
          : "border-gray-200 bg-white hover:border-emerald-300 hover:bg-emerald-50/40"
      }`}
    >
      {active && (
        <span className="absolute -top-2 -right-2 bg-emerald-600 text-white rounded-full p-0.5 shadow-sm">
          <CheckCircle2 className="w-4 h-4" />
        </span>
      )}
      {Icon && (
        <Icon className={`${compact ? "w-6 h-6" : "w-5 h-5"} shrink-0 ${active ? "text-emerald-700" : "text-gray-500"}`} />
      )}
      <div>
        <p className={`font-medium ${compact ? "text-xs leading-tight" : "text-sm"} ${active ? "text-emerald-900" : "text-gray-800"}`}>
          {label}
        </p>
        {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
      </div>
    </button>
  );
}

function NumberStepper({ label, sub, value, onChange, min = 0, max = 20, icon: Icon }) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl border border-gray-200 bg-white">
      <div className="flex items-center gap-3">
        {Icon && <Icon className="w-5 h-5 text-gray-400" />}
        <div>
          <p className="font-medium text-sm text-gray-800">{label}</p>
          {sub && <p className="text-xs text-gray-500">{sub}</p>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onChange(Math.max(min, value - 1))}
          disabled={value <= min}
          className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center text-gray-600 hover:border-emerald-500 hover:text-emerald-600 disabled:opacity-30 disabled:hover:border-gray-300 disabled:hover:text-gray-600"
        >
          <Minus className="w-4 h-4" />
        </button>
        <span className="w-6 text-center font-semibold text-gray-900 tabular-nums">{value}</span>
        <button
          type="button"
          onClick={() => onChange(Math.min(max, value + 1))}
          className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center text-gray-600 hover:border-emerald-500 hover:text-emerald-600"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function MatchBar({ label, value }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-600">{label}</span>
        <span className="text-xs text-gray-400 tabular-nums">{value}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

/* --------------------------------- main ------------------------------------ */

export default function Wizard() {
  const [step, setStep] = useState(1);
  const [data, setData] = useState({
    startDate: "",
    duration: "5",
    customDuration: "",
    arrivalAirport: "",
    totalBudget: "",
    preferredLanguage: "English",
    preferredRegion: [],
    adults: 2,
    children: 0,
    childrenAges: [],
    seniors: 0,
    groupType: "",
    accessibilityNeeds: [],
    interests: [],
    tripPace: "",
    activityLevel: "",
    mustVisit: [],
    placesToAvoid: "",
    accommodationType: "",
    hotelRating: "",
    cuisine: [],
    specialOccasion: "",
    smePreferences: [],
    aiPriority: "",
    freeText: "",
  });

  useEffect(() => {
    setData((prev) => {
      const arr = [...prev.childrenAges];
      while (arr.length < prev.children) arr.push("");
      while (arr.length > prev.children) arr.pop();
      return { ...prev, childrenAges: arr };
    });
  }, [data.children]);

  const set = (field, value) => setData((prev) => ({ ...prev, [field]: value }));

  const toggleMulti = (field, value, noPrefValue) => {
    setData((prev) => {
      const arr = prev[field];
      if (noPrefValue && value === noPrefValue) {
        return { ...prev, [field]: arr.includes(noPrefValue) ? [] : [noPrefValue] };
      }
      const next = arr.includes(value)
        ? arr.filter((v) => v !== value)
        : [...arr.filter((v) => v !== noPrefValue), value];
      return { ...prev, [field]: next };
    });
  };

  const effectiveDuration = data.duration === "Custom" ? data.customDuration : data.duration;
  const departureDate = addDays(data.startDate, effectiveDuration);

  /* ---- derived "AI understanding" indicators (heuristic, not a live backend call) ---- */
  const hotelsMatch = Math.min(100, (data.accommodationType ? 40 : 0) + (data.hotelRating ? 30 : 0) + (data.totalBudget ? 30 : 0));
  const poisMatch = Math.min(100, data.interests.length * 10);
  const eventsMatch = Math.min(100, (data.startDate ? 40 : 0) + (data.preferredRegion.length > 0 ? 30 : 0) + (effectiveDuration ? 30 : 0));
  const smesMatch = Math.min(100, data.smePreferences.length * 18);
  const restaurantsMatch = Math.min(100, data.cuisine.length * 12);

  const mandatoryFields = [data.startDate, effectiveDuration, data.arrivalAirport, data.totalBudget, data.preferredLanguage, data.groupType];
  const optionalFields = [
    data.preferredRegion.length > 0, data.accessibilityNeeds.length > 0, data.interests.length > 0,
    data.tripPace, data.activityLevel, data.mustVisit.length > 0, data.accommodationType, data.hotelRating,
    data.cuisine.length > 0, data.specialOccasion, data.smePreferences.length > 0, data.aiPriority,
    data.freeText.trim().length > 0,
  ];
  const confidence = Math.round(
    ((mandatoryFields.filter(Boolean).length / mandatoryFields.length) * 0.6 +
      (optionalFields.filter(Boolean).length / optionalFields.length) * 0.4) * 100
  );

  const tips = {
    1: "Start with the essentials — dates, budget, and airport tell me the frame I'm designing inside.",
    2: "Knowing exactly who's traveling helps me pick venues that actually fit the group.",
    3: "This is where your trip starts feeling like yours. Pick everything that's genuinely you.",
    4: "Optional, but every choice here sharpens the match between you and local SMEs.",
    5: "When two good options conflict, this tells me which one to pick.",
    6: "Anything the form couldn't capture — write it here, in any language.",
    7: "I'm ready. Here's everything I've understood about your trip.",
  };

  const canProceed = () => {
    if (step === 1) return Boolean(data.startDate && effectiveDuration && data.arrivalAirport && data.totalBudget && data.preferredLanguage);
    if (step === 2) return Boolean(data.groupType);
    if (step === 3) return Boolean(data.interests.length > 0 && data.tripPace && data.activityLevel);
    return true;
  };

  const next = () => setStep((s) => Math.min(7, s + 1));
  const back = () => setStep((s) => Math.max(1, s - 1));

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      {/* top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-emerald-700 flex items-center justify-center">
          <MapPin className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="font-semibold text-gray-900 leading-tight">ReTour</p>
          <p className="text-xs text-gray-500 leading-tight">Rediscover Jordan</p>
        </div>
        <div className="ml-6 pl-6 border-l border-gray-200 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-600" />
          <span className="font-medium text-gray-800 text-sm">AI Package Builder</span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-[220px_1fr_300px] gap-6">
        {/* left stepper */}
        <div className="hidden lg:block">
          <div className="sticky top-8 space-y-1">
            {STEPS.map((s) => {
              const done = s.id < step;
              const current = s.id === step;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => s.id < step && setStep(s.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                    current ? "bg-emerald-50" : done ? "hover:bg-gray-100" : ""
                  }`}
                >
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
                      current
                        ? "bg-emerald-600 text-white"
                        : done
                        ? "bg-emerald-600 text-white"
                        : "bg-gray-200 text-gray-500"
                    }`}
                  >
                    {done ? <CheckCircle2 className="w-4 h-4" /> : s.id}
                  </span>
                  <span className={`text-sm ${current ? "font-medium text-emerald-900" : done ? "text-gray-700" : "text-gray-400"}`}>
                    {s.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* mobile progress */}
        <div className="lg:hidden -mt-2">
          <p className="text-xs text-gray-500 mb-2">Step {step} of 7 — {STEPS[step - 1].label}</p>
          <div className="h-1.5 rounded-full bg-gray-200 overflow-hidden">
            <div className="h-full bg-emerald-600 transition-all duration-300" style={{ width: `${(step / 7) * 100}%` }} />
          </div>
        </div>

        {/* main content */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8">
          <p className="text-xs text-gray-400 mb-1">Step {step} of 7</p>

          {step === 1 && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Trip Basics</h2>
              <p className="text-sm text-gray-500 mb-6">The essentials — when, where from, and how much.</p>

              <div className="grid sm:grid-cols-2 gap-5">
                <div>
                  <Label required>Start Date</Label>
                  <div className="relative">
                    <Calendar className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="date"
                      value={data.startDate}
                      onChange={(e) => set("startDate", e.target.value)}
                      className="w-full pl-10 pr-3 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                    />
                  </div>
                </div>

                <div>
                  <Label required>Arrival Airport</Label>
                  <div className="relative">
                    <Plane className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <select
                      value={data.arrivalAirport}
                      onChange={(e) => set("arrivalAirport", e.target.value)}
                      className="w-full pl-10 pr-3 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 appearance-none bg-white"
                    >
                      <option value="">Select your arrival airport</option>
                      {AIRPORTS.map((a) => (
                        <option key={a.id} value={a.id}>{a.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="mt-5">
                <Label required>Package Duration</Label>
                <div className="flex flex-wrap gap-2">
                  {DURATIONS.map((d) => (
                    <Chip key={d} active={data.duration === d} onClick={() => set("duration", d)} label={d === "Custom" ? "Custom" : `${d} Day${d === "1" ? "" : "s"}`} />
                  ))}
                </div>
                {data.duration === "Custom" && (
                  <input
                    type="number"
                    min={1}
                    placeholder="Number of days"
                    value={data.customDuration}
                    onChange={(e) => set("customDuration", e.target.value)}
                    className="mt-3 w-40 px-3 py-2 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                )}
                {data.startDate && effectiveDuration && (
                  <p className="text-xs text-gray-400 mt-2">Departure: {departureDate}</p>
                )}
              </div>

              <div className="grid sm:grid-cols-2 gap-5 mt-5">
                <div>
                  <Label required>Total Budget (JOD)</Label>
                  <div className="relative">
                    <Wallet className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="number"
                      min={0}
                      placeholder="e.g. 900"
                      value={data.totalBudget}
                      onChange={(e) => set("totalBudget", e.target.value)}
                      className="w-full pl-10 pr-3 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">Total for the whole trip, not per person.</p>
                </div>

                <div>
                  <Label required>Preferred Language</Label>
                  <div className="relative">
                    <Globe className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <select
                      value={data.preferredLanguage}
                      onChange={(e) => set("preferredLanguage", e.target.value)}
                      className="w-full pl-10 pr-3 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 appearance-none bg-white"
                    >
                      {LANGUAGES.map((l) => (
                        <option key={l} value={l}>{l}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="mt-5">
                <Label>Preferred Region <span className="text-gray-400 font-normal">(Optional)</span></Label>
                <div className="flex flex-wrap gap-2">
                  <Chip active={data.preferredRegion.length === 0} onClick={() => set("preferredRegion", [])} label="No Preference" />
                  {REGIONS.map((r) => (
                    <Chip key={r} active={data.preferredRegion.includes(r)} onClick={() => toggleMulti("preferredRegion", r)} label={r} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Travelers</h2>
              <p className="text-sm text-gray-500 mb-6">Help the AI understand your travel group.</p>

              <div className="space-y-3">
                <NumberStepper label="Adults" value={data.adults} onChange={(v) => set("adults", v)} min={1} icon={Users} />
                <NumberStepper label="Children" sub="Ages 2–12" value={data.children} onChange={(v) => set("children", v)} icon={Baby} />

                {data.children > 0 && (
                  <div className="pl-4 border-l-2 border-emerald-100 ml-2 flex flex-wrap gap-2">
                    {data.childrenAges.map((age, i) => (
                      <input
                        key={i}
                        type="number"
                        min={0}
                        max={17}
                        placeholder={`Child ${i + 1} age`}
                        value={age}
                        onChange={(e) => {
                          const arr = [...data.childrenAges];
                          arr[i] = e.target.value;
                          set("childrenAges", arr);
                        }}
                        className="w-32 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                      />
                    ))}
                  </div>
                )}

                <NumberStepper label="Seniors" sub="Age 60+" value={data.seniors} onChange={(v) => set("seniors", v)} icon={PersonStanding} />
              </div>

              <div className="mt-6">
                <Label required>Group Type</Label>
                <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
                  {GROUP_TYPES.map((g) => (
                    <OptionCard key={g.id} compact icon={g.Icon} label={g.label} active={data.groupType === g.id} onClick={() => set("groupType", g.id)} />
                  ))}
                </div>
              </div>

              <div className="mt-6">
                <Label>Accessibility Needs <span className="text-gray-400 font-normal">(Optional)</span></Label>
                <div className="flex flex-wrap gap-2">
                  <Chip active={data.accessibilityNeeds.length === 0} onClick={() => set("accessibilityNeeds", [])} label="No Preference" />
                  {ACCESS_NEEDS.map((a) => (
                    <Chip key={a} active={data.accessibilityNeeds.includes(a)} onClick={() => toggleMulti("accessibilityNeeds", a)} label={a} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Journey Type</h2>
              <p className="text-sm text-gray-500 mb-6">Choose everything that matches your ideal experience.</p>

              <Label required>Interests</Label>
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2.5 mb-6">
                {INTERESTS.map((it) => (
                  <OptionCard
                    key={it.id}
                    compact
                    icon={it.Icon}
                    label={it.label}
                    active={data.interests.includes(it.id)}
                    onClick={() => toggleMulti("interests", it.id)}
                  />
                ))}
              </div>

              <div className="grid sm:grid-cols-2 gap-6">
                <div>
                  <Label required>Trip Pace</Label>
                  <div className="flex flex-wrap gap-2">
                    {TRIP_PACE.map((p) => (
                      <Chip key={p} active={data.tripPace === p} onClick={() => set("tripPace", p)} label={p} />
                    ))}
                  </div>
                </div>
                <div>
                  <Label required>Activity Level</Label>
                  <div className="flex flex-wrap gap-2">
                    {ACTIVITY_LEVEL.map((a) => (
                      <Chip key={a} active={data.activityLevel === a} onClick={() => set("activityLevel", a)} label={a} />
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-6">
                <Label>Must Visit <span className="text-gray-400 font-normal">(Optional)</span></Label>
                <div className="flex flex-wrap gap-2">
                  <Chip active={data.mustVisit.length === 0} onClick={() => set("mustVisit", [])} label="No Preference" />
                  {MUST_VISIT.map((m) => (
                    <Chip key={m} active={data.mustVisit.includes(m)} onClick={() => toggleMulti("mustVisit", m)} label={m} />
                  ))}
                </div>
              </div>

              <div className="mt-6">
                <Label>Places to Avoid <span className="text-gray-400 font-normal">(Optional)</span></Label>
                <input
                  type="text"
                  placeholder="e.g. crowded markets, long hikes"
                  value={data.placesToAvoid}
                  onChange={(e) => set("placesToAvoid", e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                />
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Customize Your Experience</h2>
              <p className="text-sm text-gray-500 mb-6">Optional — every answer sharpens the match. All good to skip.</p>

              <SectionTitle icon={Building2} title="Accommodation" />
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2.5 mb-4">
                {ACCOMMODATION.map((a) => (
                  <OptionCard key={a.id} compact icon={a.Icon} label={a.label} active={data.accommodationType === a.id} onClick={() => set("accommodationType", a.id)} />
                ))}
              </div>
              <div className="flex flex-wrap gap-2 mb-8">
                {HOTEL_RATING.map((r) => (
                  <Chip key={r} active={data.hotelRating === r} onClick={() => set("hotelRating", r)} label={r} />
                ))}
              </div>

              <SectionTitle icon={ChefHat} title="Dining Preferences" />
              <div className="flex flex-wrap gap-2 mb-8">
                <Chip active={data.cuisine.length === 0} onClick={() => set("cuisine", [])} label="No Preference" />
                {CUISINE.map((c) => (
                  <Chip key={c} active={data.cuisine.includes(c)} onClick={() => toggleMulti("cuisine", c)} label={c} />
                ))}
              </div>

              <SectionTitle icon={Cake} title="Special Occasion" sub="Optional" />
              <div className="flex flex-wrap gap-2 mb-8">
                {OCCASIONS.map((o) => (
                  <Chip key={o} active={data.specialOccasion === o} onClick={() => set("specialOccasion", o)} label={o} />
                ))}
              </div>

              <SectionTitle icon={HandHeart} title="SME Preferences" sub="What kind of local businesses should we favor?" />
              <div className="flex flex-wrap gap-2">
                <Chip active={data.smePreferences.length === 0} onClick={() => set("smePreferences", [])} label="No Preference" />
                {SME.map((s) => (
                  <Chip key={s} active={data.smePreferences.includes(s)} onClick={() => toggleMulti("smePreferences", s)} label={s} />
                ))}
              </div>
            </div>
          )}

          {step === 5 && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">AI Priorities</h2>
              <p className="text-sm text-gray-500 mb-6">If the AI has to make trade-offs, what should it prioritize?</p>

              <div className="grid sm:grid-cols-2 gap-3">
                {PRIORITIES.map((p) => (
                  <OptionCard key={p.id} icon={Heart} label={p.label} sub={p.desc} active={data.aiPriority === p.id} onClick={() => set("aiPriority", p.id)} />
                ))}
              </div>
            </div>
          )}

          {step === 6 && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Tell AI About Your Trip</h2>
              <p className="text-sm text-gray-500 mb-6">Share anything the form couldn't capture.</p>

              <textarea
                rows={7}
                value={data.freeText}
                onChange={(e) => set("freeText", e.target.value)}
                placeholder="We are celebrating our anniversary and would love quiet places, authentic food, and a sunset dinner near Petra."
                className="w-full px-4 py-3 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 resize-none"
              />
              <p className="text-xs text-gray-400 mt-2 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
                You can write naturally, and in any language.
              </p>
            </div>
          )}

          {step === 7 && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Review Before Building</h2>
              <p className="text-sm text-gray-500 mb-6">Here's everything the AI understood about your trip.</p>

              <div className="grid sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
                <SummaryRow label="Dates" value={data.startDate ? `${data.startDate} → ${departureDate}` : "—"} />
                <SummaryRow label="Duration" value={effectiveDuration ? `${effectiveDuration} day(s)` : "—"} />
                <SummaryRow label="Arrival Airport" value={AIRPORTS.find((a) => a.id === data.arrivalAirport)?.label || "—"} />
                <SummaryRow label="Budget" value={data.totalBudget ? `${data.totalBudget} JOD (total)` : "—"} />
                <SummaryRow label="Language" value={data.preferredLanguage || "—"} />
                <SummaryRow label="Region" value={data.preferredRegion.length ? data.preferredRegion.join(", ") : "No preference"} />
                <SummaryRow label="Travelers" value={`${data.adults} Adults, ${data.children} Children, ${data.seniors} Seniors`} />
                <SummaryRow label="Group Type" value={GROUP_TYPES.find((g) => g.id === data.groupType)?.label || "—"} />
                <SummaryRow label="Accessibility" value={data.accessibilityNeeds.length ? data.accessibilityNeeds.join(", ") : "No preference"} />
                <SummaryRow label="Interests" value={data.interests.length ? `${data.interests.length} selected` : "—"} />
                <SummaryRow label="Pace / Activity" value={`${data.tripPace || "—"} / ${data.activityLevel || "—"}`} />
                <SummaryRow label="Must Visit" value={data.mustVisit.length ? data.mustVisit.join(", ") : "No preference"} />
                <SummaryRow label="Accommodation" value={ACCOMMODATION.find((a) => a.id === data.accommodationType)?.label || "No preference"} />
                <SummaryRow label="Cuisine" value={data.cuisine.length ? data.cuisine.join(", ") : "No preference"} />
                <SummaryRow label="Occasion" value={data.specialOccasion || "None"} />
                <SummaryRow label="SME Focus" value={data.smePreferences.length ? data.smePreferences.join(", ") : "No preference"} />
                <SummaryRow label="AI Priority" value={PRIORITIES.find((p) => p.id === data.aiPriority)?.label || "—"} />
              </div>

              {data.freeText && (
                <div className="mt-5 p-4 rounded-xl bg-gray-50 border border-gray-200">
                  <p className="text-xs font-medium text-gray-500 mb-1">In your words</p>
                  <p className="text-sm text-gray-700">{data.freeText}</p>
                </div>
              )}

              <button
                type="button"
                className="mt-8 w-full py-3.5 rounded-xl bg-emerald-700 text-white font-medium flex items-center justify-center gap-2 hover:bg-emerald-800 transition-colors"
              >
                <Sparkles className="w-4 h-4" />
                Build My AI Package
              </button>
            </div>
          )}

          {/* nav buttons */}
          {step < 7 && (
            <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-100">
              <button
                type="button"
                onClick={back}
                disabled={step === 1}
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-0 disabled:pointer-events-none"
              >
                <ChevronLeft className="w-4 h-4" />
                Back
              </button>
              <button
                type="button"
                onClick={next}
                disabled={!canProceed()}
                className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-sm font-medium bg-emerald-700 text-white hover:bg-emerald-800 disabled:opacity-30 disabled:pointer-events-none"
              >
                Next: {STEPS[step]?.label}
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* right sidebar */}
        <div className="hidden lg:block">
          <div className="sticky top-8 space-y-4">
            <div className="bg-white rounded-2xl border border-gray-200 p-5">
              <p className="font-semibold text-gray-900 text-sm mb-4">Your Trip Summary</p>
              <div className="space-y-2.5 text-xs">
                <SidebarRow label="Duration" value={effectiveDuration ? `${effectiveDuration} day(s)` : "—"} />
                <SidebarRow label="Travelers" value={`${data.adults}A · ${data.children}C · ${data.seniors}S`} />
                <SidebarRow label="Budget" value={data.totalBudget ? `${data.totalBudget} JOD` : "—"} />
                <SidebarRow label="Language" value={data.preferredLanguage || "—"} />
                <SidebarRow label="Focus" value={data.interests.length ? `${data.interests.length} interests` : "—"} />
              </div>
            </div>

            <div className="bg-emerald-900 rounded-2xl p-5 text-white">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-4 h-4 text-emerald-300" />
                <p className="font-semibold text-sm">AI Assistant</p>
              </div>

              <p className="text-xs text-emerald-100/90 mb-4 leading-relaxed">{tips[step]}</p>

              <p className="text-[11px] uppercase tracking-wide text-emerald-300 mb-2">Knowledge Matches</p>
              <div className="space-y-2.5 mb-4 [&_span]:text-emerald-100 [&_.bg-gray-100]:bg-emerald-800 [&_.bg-emerald-500]:bg-emerald-300">
                <MatchBar label="Hotels" value={hotelsMatch} />
                <MatchBar label="POIs" value={poisMatch} />
                <MatchBar label="Events" value={eventsMatch} />
                <MatchBar label="SMEs" value={smesMatch} />
                <MatchBar label="Restaurants" value={restaurantsMatch} />
              </div>

              <div className="pt-4 border-t border-emerald-800 flex items-center justify-between">
                <span className="text-[11px] uppercase tracking-wide text-emerald-300">AI Confidence</span>
                <span className="text-lg font-semibold tabular-nums">{confidence}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-gray-100">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-800 font-medium text-right">{value}</span>
    </div>
  );
}

function SidebarRow({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-800 font-medium">{value}</span>
    </div>
  );
}
