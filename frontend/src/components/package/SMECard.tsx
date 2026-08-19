"use client";

import { motion } from "framer-motion";
import { Check, Compass, Sparkles } from "lucide-react";

import type { DaySME } from "@/types/package";
import styles from "@/styles/package.module.css";

export default function SMECard({ sme }: { sme: DaySME }) {
  const why = sme.matched_because || [];
  const knownFor = (sme.known_for || []).filter((line) => !why.includes(line));
  const specs = sme.specs?.length
    ? sme.specs
    : [
        sme.specializations?.length
          ? { label: "Specializations", value: sme.specializations.join(", ") }
          : null,
        sme.languages?.length ? { label: "Languages", value: sme.languages.join(", ") } : null,
        sme.experience_years ? { label: "Experience", value: `${sme.experience_years} years` } : null,
      ].filter((row): row is { label: string; value: string } => Boolean(row));

  return (
    <motion.article
      className={styles.smeCard}
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.35 }}
    >
      <div className={styles.dayBadge}>{sme.role || sme.sme_type}</div>
      <h4>{sme.name}</h4>
      <p>
        <Compass size={14} /> {sme.location || "Jordan"}
        {sme.experience_type ? ` · ${sme.experience_type}` : ""}
        {sme.covers_regions?.length ? ` · Covers ${sme.covers_regions.join(", ")}` : ""}
      </p>
      {sme.matched_because?.length ? (
        <div>
          <p className={styles.specLabel}>
            <Sparkles size={13} /> Why they fit this trip
          </p>
          <ul className={styles.matchList}>
            {sme.matched_because.slice(0, 4).map((reason) => (
              <li key={reason}>
                <Check size={14} className={styles.check} /> {reason}
              </li>
            ))}
          </ul>
        </div>
      ) : sme.reason ? (
        <p className={styles.reason}>{sme.reason}</p>
      ) : null}
      {knownFor.length ? (
        <div>
          <p className={styles.specLabel}>
            <Sparkles size={13} /> What they are distinguished by
          </p>
          <ul className={styles.matchList}>
            {knownFor.slice(0, 4).map((reason) => (
              <li key={reason}>
                <Check size={14} className={styles.check} /> {reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {specs.length ? (
        <dl className={styles.specList}>
          {specs.slice(0, 6).map((spec) => (
            <div key={`${spec.label}-${spec.value}`}>
              <dt>{spec.label}</dt>
              <dd>{spec.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </motion.article>
  );
}
