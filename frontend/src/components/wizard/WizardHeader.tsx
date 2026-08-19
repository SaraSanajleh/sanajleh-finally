"use client";

import styles from "@/styles/wizard/wizard.module.css";


type Props = {

    currentStep: number;

    totalSteps: number;

    onNext: () => void;

    onBack: () => void;

};

const titles = [

    "",

    "Trip Basics",

    "Travelers",

    "Journey Type",

    "Customize",

    "AI Priorities",

    "Tell AI",

    "Review & Build",

];

const descriptions = [

    "",

    "Let's start with your travel details.",

    "Tell us who's travelling.",

    "Select your travel style.",

    "Accommodation and preferences.",

    "What matters most to you?",

    "Anything else the AI should know?",

    "Review everything before generating.",

];

export default function WizardHeader({

    currentStep,

    totalSteps,

    onNext,

    onBack,

}: Props) {

    const progress =

        (currentStep / totalSteps) * 100;

    return (

        <>

            <div className={styles.header}>

                <div>


                    <span className={styles.stepBadge}>

                        Step {currentStep} of {totalSteps}

                    </span>

                    <h2>

                        {titles[currentStep]}

                    </h2>

                    <p>

                        {descriptions[currentStep]}

                    </p>

                </div>

                <button
                    type="button"
                    className="btn btn-outline-success"
                    onClick={() => {
                        window.location.href = "/";
                    }}
                >
                    Save & Exit
                </button>

            </div>

            <div className={styles.progressContainer}>

                <div className={styles.progressBar}>

                    <div

                        className={styles.progressFill}

                        style={{

                            width: `${progress}%`

                        }}

                    />

                </div>

            </div>



        </>

    );

}