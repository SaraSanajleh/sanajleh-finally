"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

import type { DayPlan, PackageGenerationResult, TourismPackage } from "@/types/package";
import { unwrapPackage } from "@/types/package";
import SMECard from "./SMECard";
import styles from "@/styles/package.module.css";

const TripMap = dynamic(() => import("./TripMap"), { ssr: false });

function isArrivalDay(day: { is_arrival_day?: boolean; theme?: string }) {
  if (day.is_arrival_day) {
    return true;
  }
  return (day.theme || "").toLowerCase().startsWith("arrival");
}

function dayLabel(day: DayPlan, days: DayPlan[]) {
  if (isArrivalDay(day)) {
    return "Arrival";
  }
  let exploring = 0;
  for (const item of days) {
    if (isArrivalDay(item)) {
      continue;
    }
    exploring += 1;
    if (item === day || (item.day === day.day && item.date === day.date)) {
      return `Day ${exploring}`;
    }
  }
  return `Day ${day.day}`;
}

function looksLikeSystemDump(text: string) {
  const lower = text.toLowerCase();
  return (
    lower.includes("each day stays in one area") ||
    lower.includes("a route built around your interests") ||
    lower.includes("your first night is near the airport") ||
    lower.includes("about 3 places to visit") ||
    (text.match(/:\s/g) || []).length >= 2
  );
}

function joinPlaces(names: string[]) {
  const unique = [...new Set(names.filter(Boolean))];
  if (!unique.length) {
    return "Jordan";
  }
  if (unique.length === 1) {
    return unique[0];
  }
  if (unique.length === 2) {
    return `${unique[0]} and ${unique[1]}`;
  }
  return `${unique.slice(0, -1).join(", ")}, and ${unique[unique.length - 1]}`;
}

function plannerNote(pkg: TourismPackage, days: DayPlan[]) {
  const raw = (pkg.explanations?.trip_planning_reason || pkg.planning?.strategy || "").trim();
  if (raw && !looksLikeSystemDump(raw)) {
    return raw;
  }
  const arrival = days.find(isArrivalDay);
  const exploring = days.filter((day) => !isArrivalDay(day));
  const loop = joinPlaces(exploring.map((day) => day.region || "").filter(Boolean));
  const city = arrival?.region || "Amman";
  const parts = [
    `Arrival night stays in ${city} — hotel, a meal, rest. Touring starts the next morning.`,
  ];
  if (loop && loop !== "Jordan") {
    parts.push(`The exploring days stay on a short loop: ${loop}.`);
  }
  return parts.join(" ");
}

function tripSmes(pkg: TourismPackage) {
  const recommended = pkg.sme_value?.recommended || [];
  const seen = new Set<string>();
  return recommended.filter((sme) => {
    if (!sme.sme_id || seen.has(sme.sme_id)) {
      return false;
    }
    seen.add(sme.sme_id);
    return true;
  });
}

export default function PackageExperience({ result }: { result: unknown }) {
  const pkg = unwrapPackage(result);
  const meta = (result as PackageGenerationResult | null)?.metadata;
  if (!pkg) {
    return null;
  }

  const title = pkg.trip?.title || pkg.trip_title || "Your Jordan journey";
  const days = pkg.days || [];
  const smes = tripSmes(pkg);
  const exploringDays = days.filter((day) => !isArrivalDay(day)).length;
  const note = plannerNote(pkg, days);

  return (
    <article className={styles.experience}>
      <header className={styles.hero}>
        <div className={styles.kicker}>
          <Sparkles size={14} /> Personalized by ReTour Brain
        </div>
        <h1>{title}</h1>
        <p>{pkg.trip?.summary || pkg.welcome_message}</p>
        <div className={styles.statRow}>
          <div className={styles.stat}>
            <span>Duration</span>
            <strong>
              {days.some(isArrivalDay)
                ? `Arrival + ${exploringDays} exploring ${exploringDays === 1 ? "day" : "days"} · ${pkg.trip?.nights ?? 0} nights`
                : `${pkg.trip?.duration_days || days.length} days · ${pkg.trip?.nights ?? 0} nights`}
            </strong>
          </div>
          <div className={styles.stat}>
            <span>Travelers</span>
            <strong>{pkg.traveler_profile?.total_travelers || 1}</strong>
          </div>
          <div className={styles.stat}>
            <span>Regions</span>
            <strong>{(pkg.trip?.regions || []).join(", ") || "Jordan"}</strong>
          </div>
          <div className={styles.stat}>
            <span>Budget band</span>
            <strong>{pkg.budget?.band || "stated budget"}</strong>
          </div>
        </div>
      </header>

      <div className={styles.body}>
        <div className={styles.grid2}>
          <TripMap days={days} />
          <aside className={styles.panel}>
            <h3 className={styles.sectionTitle}>Planner&apos;s note</h3>
            <p className={styles.sectionLead}>{note}</p>
          </aside>
        </div>

        {pkg.warnings?.length ? (
          <div className={styles.warn}>
            {pkg.warnings.map((warning) => warning.message).join(" · ")}
          </div>
        ) : null}

        <section>
          <h2 className={styles.sectionTitle}>The itinerary</h2>
          <div className={styles.days}>
            {days.map((day, index) => (
              <motion.section
                key={`${day.day}-${day.date}`}
                className={styles.dayCard}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.4, delay: index * 0.04 }}
              >
                <div className={styles.dayHead}>
                  <div>
                    <span className={styles.dayBadge}>{dayLabel(day, days)}</span>
                    <h3 className={styles.sectionTitle}>{day.theme || day.region || dayLabel(day, days)}</h3>
                    <p className={styles.sectionLead}>
                      {day.date} {day.region ? `· ${day.region}` : ""}
                    </p>
                    <p>{day.summary}</p>
                  </div>
                </div>
                <div className={styles.timeline}>
                  {(day.schedule || []).map((item) => (
                    <div key={`${item.item_id}-${item.time}-${item.name}`} className={styles.itemCard}>
                      <div className={styles.timeCol}>
                        {item.type === "hotel" && !item.time
                          ? "Tonight"
                          : `${item.time || item.slot || "—"}${item.end_time ? ` – ${item.end_time}` : ""}`}
                        <div className={styles.typePill}>{item.type || "stop"}</div>
                      </div>
                      <div>
                        <h4>{item.name}</h4>
                        <p>{item.location}</p>
                        {item.description ? <p>{item.description}</p> : null}
                        {item.reason ? <p className={styles.reason}>{item.reason}</p> : null}
                      </div>
                    </div>
                  ))}
                </div>
              </motion.section>
            ))}
          </div>
        </section>

        <section className={styles.panel}>
          <h2 className={styles.sectionTitle}>
            {pkg.sme_value?.headline || "Local businesses recommended for this trip"}
          </h2>
          <p className={styles.sectionLead}>
            {pkg.sme_value?.summary ||
              pkg.explanations?.why_smes?.[0] ||
              "One local guide and one tour operator for the whole trip."}
          </p>
          <div className={styles.smeGrid}>
            {smes.length ? smes.map((sme) => <SMECard key={sme.sme_id} sme={sme} />) : (
              <p>No matching local businesses were found in the SME directory for this profile.</p>
            )}
          </div>
        </section>

        <section className={styles.panel}>
          <h2 className={styles.sectionTitle}>Budget</h2>
          <p className={styles.sectionLead}>{pkg.budget?.disclaimer}</p>
          <p>
            Your ceiling: {pkg.budget?.traveler_budget ?? "—"} {pkg.budget?.currency || "JOD"}
            {pkg.budget?.estimated_total && pkg.budget.estimated_total !== "not_available"
              ? ` · Listed pieces: ${pkg.budget.estimated_total}`
              : ""}
          </p>
          {(pkg.budget?.items || []).map((item) => (
            <p key={`${item.category}-${item.estimated_cost}`}>
              <strong>{item.category}</strong>: {item.estimated_cost || "not_available"}
              {item.notes ? ` — ${item.notes}` : ""}
            </p>
          ))}
          {meta?.caseId ? (
            <p className={styles.sectionLead}>Case {meta.caseId}</p>
          ) : null}
        </section>
      </div>
    </article>
  );
}
