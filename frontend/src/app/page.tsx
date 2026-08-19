"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import styles from "./page.module.css";
import { MapPin } from "lucide-react";

interface HeroSlide {
    id: string;
    image: string;
    eyebrow: string;
    title: string;
    highlightedText: string;
    description: string;
    location: string;
}

const heroSlides: HeroSlide[] = [
    {
        id: "petra",
        image: "/images/hero/petra-hero.png",
        eyebrow: "AI-Powered Travel Planning",
        title: "Rediscover Jordan with",
        highlightedText: "AI",
        description:
            "Create personalized journeys tailored to your interests, travel style, and budget, supported by trusted local tourism providers.",
        location: "Petra",
    },
    {
        id: "wadi-rum",
        image: "/images/hero/wadi-rum-hero.png",
        eyebrow: "Authentic Desert Experiences",
        title: "Experience the Magic of",
        highlightedText: "Wadi Rum",
        description:
            "Explore dramatic desert landscapes, Bedouin culture, stargazing experiences, jeep tours, camps, and local adventures designed around you.",
        location: "Wadi Rum",
    },
    {
        id: "dead-sea",
        image: "/images/hero/dead-sea-hero.png",
        eyebrow: "Wellness and Relaxation",
        title: "Relax Beside the",
        highlightedText: "Dead Sea",
        description:
            "Build a peaceful Jordan itinerary with wellness resorts, spa treatments, scenic dining, nature, and personalized transportation.",
        location: "Dead Sea",
    },
];

const features = [
    {
        icon: "bi-stars",
        title: "AI Personalized",
        description: "Itineraries created around your exact preferences.",
    },
    {
        icon: "bi-people-fill",
        title: "Local SMEs",
        description: "Supporting trusted tourism businesses across Jordan.",
    },
    {
        icon: "bi-shield-check",
        title: "Secure & Trusted",
        description: "Verified partners and protected trip information.",
    },
    {
        icon: "bi-geo-alt",
        title: "Authentic Experiences",
        description: "Real culture, local services, and meaningful journeys.",
    },
];

const howItWorksSteps = [
    {
        icon: "bi-chat-dots",
        title: "Share Your Preferences",
        description:
            "Tell us about your travel dates, interests, budget, and travel style.",
    },
    {
        icon: "bi-stars",
        title: "AI Builds Your Trip",
        description:
            "ReTour AI creates a personalized itinerary using trusted local tourism data.",
    },
    {
        icon: "bi-sliders",
        title: "Review & Personalize",
        description:
            "Adjust hotels, activities, restaurants, and experiences until everything feels right.",
    },
    {
        icon: "bi-check2-circle",
        title: "Travel with Confidence",
        description:
            "Receive your personalized Jordan itinerary and start planning your journey.",
    },
];
const testimonials = [
    {
        rating: 5,
        quote:
            "ReTour planned our Jordan trip perfectly. Petra, Wadi Rum, and the Dead Sea — everything was beyond amazing.",
        name: "Sarah Johnson",
        location: "USA",
        avatarColor: "",
    },
    {
        rating: 5,
        quote:
            "The AI suggestions were spot on. We discovered hidden gems we would have never found on our own.",
        name: "Ahmed Al-Mansour",
        location: "UAE",
        avatarColor: "amber",
    },
    {
        rating: 5,
        quote:
            "Supporting local SMEs made the experience even more meaningful. Highly recommended.",
        name: "Maria Garcia",
        location: "Spain",
        avatarColor: "blue",
    },
];

const footerColumns = [
    {
        title: "Company",
        links: ["About Us", "How It Works", "Careers", "Blog", "Contact Us"],
    },
    {
        title: "For Travelers",
        links: ["Packages", "Experiences", "Travel Guide", "FAQs"],
    },
    {
        title: "For SMEs",
        links: ["Partner With Us", "Resources", "Success Stories", "Login"],
    },
    {
        title: "Legal",
        links: [
            "Terms & Conditions",
            "Privacy Policy",
            "Cancellation Policy",
            "Cookies Policy",
        ],
    },
];

export default function Home() {
    const [activeSlide, setActiveSlide] = useState(0);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (isPaused) {
            return;
        }

        const interval = window.setInterval(() => {
            setActiveSlide((currentSlide) =>
                currentSlide === heroSlides.length - 1 ? 0 : currentSlide + 1,
            );
        }, 6000);

        return () => window.clearInterval(interval);
    }, [isPaused]);

    const showPreviousSlide = () => {
        setActiveSlide((currentSlide) =>
            currentSlide === 0 ? heroSlides.length - 1 : currentSlide - 1,
        );
    };

    const showNextSlide = () => {
        setActiveSlide((currentSlide) =>
            currentSlide === heroSlides.length - 1 ? 0 : currentSlide + 1,
        );
    };

    const currentSlide = heroSlides[activeSlide];

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <nav className={styles.navbar} aria-label="Main navigation">
                    <Link href="/" className={styles.brand}>

                        <div className={styles.logoIcon}>
                            <MapPin size={18} />
                        </div>

                        <div className={styles.logoSection}>
                            <h5>ReTour</h5>
                            <span>Rediscover Jordan</span>
                        </div>

                    </Link>

                    <div className={styles.navLinks}>
                        <Link
                            href="/"
                            className={`${styles.navLink} ${styles.activeLink}`}
                        >
                            Home
                        </Link>

                        <Link href="/ready-packages" className={styles.navLink}>
                            Ready Packages
                        </Link>

                        <Link href="/experiences" className={styles.navLink}>
                            Experiences
                        </Link>

                        <Link href="/about" className={styles.navLink}>
                            About Us
                        </Link>

                        <Link href="/for-smes" className={styles.navLink}>
                            For SMEs
                        </Link>

                        <Link href="/contact" className={styles.navLink}>
                            Contact
                        </Link>
                    </div>

                    <div className={styles.navActions}>
                        <button
                            type="button"
                            className={styles.languageButton}
                            aria-label="Change language"
                        >
                            <i className="bi bi-globe2" />
                            <span>EN</span>
                            <i className="bi bi-chevron-down" />
                        </button>

                        <Link href="/login" className={styles.signInButton}>
                            <i className="bi bi-person" />
                            Sign In
                        </Link>
                        <Link href="/register" className={styles.signUpButton}>
                            Sign Up
                        </Link>
                    </div>
                </nav>
            </header>

            <section
                className={styles.hero}
                onMouseEnter={() => setIsPaused(true)}
                onMouseLeave={() => setIsPaused(false)}
                aria-label="Jordan destinations"
            >
                <div className={styles.backgroundSlides} aria-hidden="true">
                    {heroSlides.map((slide, index) => (
                        <div
                            key={slide.id}
                            className={`${styles.backgroundSlide} ${index === activeSlide ? styles.activeBackground : ""
                                }`}
                            style={{ backgroundImage: `url("${slide.image}")` }}
                        />
                    ))}
                </div>

                <div className={styles.heroOverlay} />

                <div className={styles.heroContent}>
                    <div key={currentSlide.id} className={styles.animatedContent}>
                        <span className={styles.aiBadge}>
                            <i className="bi bi-stars" />
                            {currentSlide.eyebrow}
                        </span>

                        <h1 className={styles.heroTitle}>
                            {currentSlide.title}
                            <br />
                            <span>{currentSlide.highlightedText}</span>
                        </h1>

                        <p className={styles.heroDescription}>
                            {currentSlide.description}
                        </p>

                        <div className={styles.heroActions}>
                            <Link
                                href="/wizard?mode=ai_builder"
                                className={styles.primaryButton}
                            >
                                <i className="bi bi-stars" />
                                Build My AI Trip
                            </Link>

                            <Link
                                href="/wizard?mode=ready_packages"
                                className={styles.secondaryButton}
                            >
                                Browse Ready Packages
                            </Link>
                        </div>

                        <div className={styles.socialProof}>
                            <div className={styles.avatars} aria-hidden="true">
                                <span>A</span>
                                <span>M</span>
                                <span>S</span>
                                <span>R</span>
                            </div>

                            <p>
                                <strong>2.5K+</strong> travelers planned journeys with ReTour
                            </p>
                        </div>
                    </div>
                </div>

                <div className={styles.sliderControls}>
                    <button
                        type="button"
                        className={styles.arrowButton}
                        onClick={showPreviousSlide}
                        aria-label="Show previous destination"
                    >
                        <i className="bi bi-chevron-left" />
                    </button>

                    <div className={styles.slideIndicators}>
                        {heroSlides.map((slide, index) => (
                            <button
                                key={slide.id}
                                type="button"
                                className={`${styles.indicator} ${index === activeSlide ? styles.activeIndicator : ""
                                    }`}
                                onClick={() => setActiveSlide(index)}
                                aria-label={`Show ${slide.location}`}
                                aria-current={index === activeSlide ? "true" : undefined}
                            />
                        ))}
                    </div>

                    <button
                        type="button"
                        className={styles.arrowButton}
                        onClick={showNextSlide}
                        aria-label="Show next destination"
                    >
                        <i className="bi bi-chevron-right" />
                    </button>
                </div>

                <span className={styles.locationBadge}>
                    <i className="bi bi-geo-alt-fill" />
                    {currentSlide.location}, Jordan
                </span>
            </section>

            <section className={styles.featureBar} aria-label="ReTour benefits">
                {features.map((feature) => (
                    <article key={feature.title} className={styles.feature}>
                        <span className={styles.featureIcon}>
                            <i className={`bi ${feature.icon}`} />
                        </span>

                        <div>
                            <h2>{feature.title}</h2>
                            <p>{feature.description}</p>
                        </div>
                    </article>
                ))}
            </section>

            <section className={styles.howItWorks} aria-label="How ReTour works">
                <h2 className={styles.sectionTitle}>How ReTour Works</h2>

                <div className={styles.stepsRow}>
                    {howItWorksSteps.map((step, index) => (
                        <div key={step.title} className={styles.step}>
                            <span className={styles.stepIconWrap}>
                                <i className={`bi ${step.icon}`} />
                            </span>

                            <h3>{step.title}</h3>
                            <p>{step.description}</p>
                        </div>
                    ))}
                </div>
            </section>

            <section className={styles.chooseSection} aria-label="Choose your experience">
                <div className={styles.chooseInner}>
                    <h2 className={`${styles.sectionTitle} ${styles.centerTitle}`}>Choose Your Experience</h2>

                    <div className={styles.experienceCards}>
                        <Link href="/ai-builder?mode=browse" className={styles.expCard}>
                            <div className={styles.expCardHeader}>
                                <span className={styles.expCardIcon}>
                                    <i className="bi bi-briefcase-fill" />
                                </span>
                                <div>
                                    <h3>Browse Ready Packages</h3>
                                    <p>
                                        Tell us your preferences and we&apos;ll match you with
                                        professionally designed packages from trusted Jordanian
                                        tourism providers, then personalize the one you pick.
                                    </p>
                                </div>
                            </div>

                            <ul className={styles.expCardFeatures}>
                                <li><i className="bi bi-check-circle-fill" />Ready-made itineraries</li>
                                <li><i className="bi bi-check-circle-fill" />Trusted local SMEs</li>
                                <li><i className="bi bi-check-circle-fill" />Instant recommendations</li>
                                <li><i className="bi bi-check-circle-fill" />Personalized to your picks</li>
                            </ul>

                            <div className={styles.expCardBtn}>
                                <span className={styles.expBtnText}>
                                    Explore Packages
                                    <i className="bi bi-arrow-right" />
                                </span>
                            </div>
                        </Link>

                        <Link
                            href="/ai-builder?mode=build"
                            className={`${styles.expCard} ${styles.expCardAI}`}
                        >
                            <div className={styles.expCardHeader}>
                                <span className={`${styles.expCardIcon} ${styles.expCardIconAI}`}>
                                    <i className="bi bi-stars" />
                                </span>
                                <div>
                                    <h3>AI Package Builder</h3>
                                    <p>
                                        Create a completely personalized itinerary from scratch,
                                        built entirely around your interests, budget, travel
                                        style, and preferences.
                                    </p>
                                </div>
                            </div>

                            <ul className={styles.expCardFeatures}>
                                <li><i className="bi bi-check-circle-fill" />Personalized itinerary</li>
                                <li><i className="bi bi-check-circle-fill" />AI recommendations</li>
                                <li><i className="bi bi-check-circle-fill" />Local experiences</li>
                                <li><i className="bi bi-check-circle-fill" />Flexible planning</li>
                            </ul>

                            <div className={styles.expCardBtn}>
                                <span className={styles.expBtnText}>Start Building</span>
                                <span className={styles.expBtnArrow}>
                                    <i className="bi bi-arrow-right" />
                                </span>
                            </div>
                        </Link>
                    </div>
                </div>
            </section>

            <section className={styles.testimonialsSection} aria-label="Traveler testimonials">
                <div className={styles.testimonialsInner}>
                    <h2 className={styles.sectionTitle}>Loved by Travelers</h2>

                    <div className={styles.testimonialsGrid}>
                        {testimonials.map((t) => (
                            <article key={t.name} className={styles.testimonialCard}>
                                <div className={styles.stars} aria-label={`${t.rating} out of 5 stars`}>
                                    {Array.from({ length: t.rating }).map((_, i) => (
                                        <i key={i} className="bi bi-star-fill" />
                                    ))}
                                </div>

                                <blockquote>&ldquo;{t.quote}&rdquo;</blockquote>

                                <div className={styles.testimonialAuthor}>
                                    <span
                                        className={`${styles.authorAvatar} ${t.avatarColor ? styles[t.avatarColor] : ""
                                            }`}
                                    >
                                        {t.name.charAt(0)}
                                    </span>
                                    <div>
                                        <p className={styles.authorName}>{t.name}</p>
                                        <p className={styles.authorMeta}>{t.location}</p>
                                    </div>
                                </div>
                            </article>
                        ))}
                    </div>
                </div>
            </section>

            <footer className={styles.footer}>
                <div className={styles.footerInner}>
                    <div className={styles.footerTop}>
                        <div className={styles.footerBrand}>
                            <Link href="/" className={styles.footerLogo}>

                                <div className={styles.logoIcon}>
                                    <MapPin size={18} />
                                </div>

                                <div className={styles.logoSection}>
                                    <h5>ReTour</h5>
                                    <span>Rediscover Jordan</span>
                                </div>

                            </Link>

                            <p className={styles.footerDesc}>
                                AI-powered travel planning platform supporting local SMEs and
                                creating unforgettable experiences in Jordan.
                            </p>

                            <div className={styles.footerSocials}>
                                <a href="#" aria-label="Instagram"><i className="bi bi-instagram" /></a>
                                <a href="#" aria-label="Facebook"><i className="bi bi-facebook" /></a>
                                <a href="#" aria-label="Twitter"><i className="bi bi-twitter" /></a>
                                <a href="#" aria-label="YouTube"><i className="bi bi-youtube" /></a>
                            </div>
                        </div>

                        {footerColumns.map((col) => (
                            <div key={col.title} className={styles.footerCol}>
                                <h4>{col.title}</h4>
                                <ul>
                                    {col.links.map((link) => (
                                        <li key={link}>
                                            <a href="#">{link}</a>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>

                    <div className={styles.footerBottom}>
                        © {new Date().getFullYear()} ReTour. All rights reserved.
                    </div>
                </div>
            </footer>
        </main>
    );
}