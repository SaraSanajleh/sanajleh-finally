"use client";

import Link from "next/link";
import { ArrowRight, BadgeCheck, MapPin, Users } from "lucide-react";
import styles from "@/styles/package.module.css";

export default function ForSmesPage() {
  return (
    <main className={styles.experience}>
      <header className={styles.hero}>
        <div className={styles.kicker}>SME growth is the core of ReTour</div>
        <h1>Reach travelers who actually want what you offer</h1>
        <p>
          ReTour does not spray advertisements. When a traveler’s preferences,
          region, and itinerary match your services, the Brain can recommend
          your guide or tour company as part of a real Jordan journey.
        </p>
        <Link href="/wizard" className={styles.dayBadge}>
          Preview a matched itinerary <ArrowRight size={14} />
        </Link>
      </header>
      <section className={styles.body}>
        <h2 className={styles.sectionTitle}>Why join ReTour</h2>
        <p className={styles.sectionLead}>
          Tourist relevance always comes first. A subscribed business is never
          inserted into an itinerary unless it is a genuine fit.
        </p>
        <div className={styles.smeGrid}>
          <article className={styles.smeCard}>
            <Users />
            <h4>Qualified demand</h4>
            <p>Recommendations use traveler interests, group type, language, and destination.</p>
          </article>
          <article className={styles.smeCard}>
            <BadgeCheck />
            <h4>Evidence, not invention</h4>
            <p>Only SMEs in the Jordan directory can be recommended. No invented businesses.</p>
          </article>
          <article className={styles.smeCard}>
            <MapPin />
            <h4>Placed in the journey</h4>
            <p>Guides and operators appear on the day and in the region where they actually work.</p>
          </article>
        </div>
      </section>
    </main>
  );
}
