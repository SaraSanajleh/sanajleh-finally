"use client";

import { motion } from "framer-motion";

import styles from "@/styles/package.module.css";

const STAGES = [
  { key: "normalize", label: "Understanding your trip" },
  { key: "context", label: "Building planning context" },
  { key: "knowledge", label: "Retrieving Jordan tourism knowledge" },
  { key: "sme", label: "Matching local tourism businesses" },
  { key: "plan", label: "Planning your itinerary" },
  { key: "validate", label: "Validating the package" },
];

export default function GenerationProgress({
  stage,
  label,
  elapsedSec,
}: {
  stage?: string;
  label?: string;
  elapsedSec: number;
}) {
  const activeIndex = Math.max(
    STAGES.findIndex((item) => item.key === stage),
    0,
  );

  return (
    <section className={styles.progress}>
      <div className={styles.kicker}>ReTour Brain</div>
      <h2 className={styles.sectionTitle}>Designing your Jordan journey</h2>
      <p className={styles.sectionLead}>
        {label || STAGES[activeIndex]?.label} · {elapsedSec}s
      </p>
      <div className={styles.progressTrack}>
        {STAGES.map((item, index) => {
          const active = index <= activeIndex;
          return (
            <motion.div
              key={item.key}
              className={`${styles.stage} ${active ? styles.stageActive : ""}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <span className={styles.dot} />
              <span>{item.label}</span>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
