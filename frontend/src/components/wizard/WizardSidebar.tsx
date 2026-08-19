"use client";

import {
    CalendarDays,
    Users,
    Compass,
    SlidersHorizontal,
    Sparkles,
    MessageSquareText,
    CircleCheckBig,
    MapPin,
} from "lucide-react";

import styles from "@/styles/wizard/wizard.module.css";
import Link from "next/link";

type Props = {
    currentStep: number;
    onStepSelect?: (step: number) => void;
};

const steps = [
    { id: 1, title: "Trip Basics", icon: CalendarDays },
    { id: 2, title: "Travelers", icon: Users },
    { id: 3, title: "Journey Type", icon: Compass },
    { id: 4, title: "Customize", icon: SlidersHorizontal },
    { id: 5, title: "AI Priorities", icon: Sparkles },
    { id: 6, title: "Tell AI", icon: MessageSquareText },
    { id: 7, title: "Review & Build", icon: CircleCheckBig },
];

export default function WizardSidebar({ currentStep, onStepSelect }: Props) {
    return (
        <aside className={styles.sidebar}>
            {/* Logo */}
            <div className={styles.sidebarTop}>

                <div className={styles.logoSection}>
                    <div className={styles.logoIcon}>
                        <MapPin size={18} />
                    </div>

                    <div>
                        <h5>ReTour</h5>
                        <span>Rediscover Jordan</span>
                    </div>
                </div>

                <Link href="/" className={styles.backHomeLink}>

                    <div className={styles.backHomeCircle}>
                        <i className="bi bi-arrow-left"></i>
                    </div>

                    <span>Back to Home</span>

                </Link>

                <nav className={styles.steps}>
                    {steps.map((step) => {
                        const Icon = step.icon;

                        return (
                            <button
                                key={step.id}
                                type="button"
                                className={`${styles.stepButton} ${currentStep === step.id ? styles.activeStep : ""
                                    }`}
                                onClick={() => onStepSelect?.(step.id)}
                            >
                                <div className={styles.stepCircle}>
                                    <Icon size={16} />
                                </div>

                                <span>{step.title}</span>
                            </button>
                        );
                    })}
                </nav>

            </div>
            {/* AI Assistant */}

            <div className={styles.aiAssistant}>
                <div className={styles.aiHeader}>
                    <Sparkles size={16} />

                    <span>AI Assistant</span>
                </div>

                <p>
                    Start with the essentials — dates, budget and region to let the AI
                    create the perfect itinerary.
                </p>
            </div>
        </aside >
    );
}