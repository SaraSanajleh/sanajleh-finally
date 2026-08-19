"use client";

import { useEffect, useState } from "react";

import { BrainStatus, checkBrainHealth, generatePackage } from "@/lib/api";
import { WizardMode, WizardState } from "@/types/wizard";

import WizardSidebar from "./WizardSidebar";
import WizardHeader from "./WizardHeader";

import Step1 from "./steps/Step1";
import Step2 from "./steps/Step2";
import Step3 from "./steps/Step3";
import Step4 from "./steps/Step4";
import Step5 from "./steps/Step5";
import Step6 from "./steps/Step6";
import Step7 from "./steps/Step7";

import RagKnowledgePanel from "./RagKnowledgePanel";
import PackageExperience from "@/components/package/PackageExperience";
import GenerationProgress from "@/components/package/GenerationProgress";

import styles from "@/styles/wizard/wizard.module.css";

type Props = {

    mode?: WizardMode;

};

export default function ReTourWizard({

    mode = "ai_builder",

}: Props) {

    const totalSteps = 7;

    const [wizard, setWizard] = useState<WizardState>({

        mode,

        step: 1,

        data: {

            startDate: "",

            duration: "1",

            customDuration: "",

            arrivalAirport: "",

            arrivalTime: "",

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

        },

    });

    const [isGenerating, setIsGenerating] = useState(false);
    const [packageResult, setPackageResult] = useState<unknown>(null);
    const [generateError, setGenerateError] = useState<string | null>(null);
    const [brainStatus, setBrainStatus] = useState<BrainStatus | null>(null);
    const [elapsedSec, setElapsedSec] = useState(0);
    const [brainStage, setBrainStage] = useState("normalize");
    const [brainStageLabel, setBrainStageLabel] = useState("Understanding your trip");

    useEffect(() => {
        if (wizard.step !== totalSteps) {
            return;
        }

        checkBrainHealth().then(setBrainStatus);
    }, [wizard.step, totalSteps]);

    useEffect(() => {
        if (!isGenerating) {
            setElapsedSec(0);
            return;
        }

        const started = Date.now();
        const timer = window.setInterval(() => {
            setElapsedSec(Math.floor((Date.now() - started) / 1000));
        }, 1000);

        return () => window.clearInterval(timer);
    }, [isGenerating]);

    function updateField<K extends keyof WizardState["data"]>(

        field: K,

        value: WizardState["data"][K]

    ) {

        setWizard((prev) => ({

            ...prev,

            data: {

                ...prev.data,

                [field]: value,

            },

        }));

    }

    function nextStep() {

        if (wizard.step < totalSteps) {

            setWizard((prev) => ({

                ...prev,

                step: prev.step + 1,

            }));

        }

    }

    function previousStep() {

        if (wizard.step > 1) {

            setWizard((prev) => ({

                ...prev,

                step: prev.step - 1,

            }));

        }

    }

    async function handleContinue() {
        if (wizard.step < totalSteps) {
            nextStep();
            return;
        }

        setIsGenerating(true);
        setGenerateError(null);
        setPackageResult(null);

        try {
            const health =
                brainStatus?.api === "ok" && brainStatus.llm === "ok"
                    ? brainStatus
                    : await checkBrainHealth();
            setBrainStatus(health);

            if (health.api === "down") {
                throw new Error(
                    "Cannot reach ReTour Brain API. Start backend: .venv\\Scripts\\uvicorn.exe app.main:app --reload --port 8000",
                );
            }

            if (health.llm !== "ok") {
                throw new Error(
                    `LLM not ready (${health.model ?? "gpt-oss:20b-cloud"}). Sign in: ollama signin && ollama pull gpt-oss:20b-cloud`,
                );
            }

            const result = await generatePackage(wizard.mode, wizard.data, (info) => {
                if (info.stage) {
                    setBrainStage(info.stage);
                }
                if (info.stageLabel) {
                    setBrainStageLabel(info.stageLabel);
                }
            });
            setPackageResult(result);
        } catch (error) {
            const message =
                error instanceof Error ? error.message : "Package generation failed";
            setGenerateError(message);
            setPackageResult({ error: message });
        } finally {
            setIsGenerating(false);
        }
    }

    function renderStep() {

        switch (wizard.step) {

            case 1:
                return (
                    <Step1
                        data={wizard.data}
                        updateField={updateField}
                    />
                );

            case 2:
                return (
                    <Step2
                        data={wizard.data}
                        updateField={updateField}
                    />
                );

            case 3:
                return (
                    <Step3
                        data={wizard.data}
                        updateField={updateField}
                    />
                );

            case 4:
                return (
                    <Step4
                        data={wizard.data}
                        updateField={updateField}
                    />
                );

            case 5:
                return (
                    <Step5
                        data={wizard.data}
                        updateField={updateField}
                    />
                );

            case 6:
                return (
                    <Step6
                        data={wizard.data}
                        updateField={updateField}
                    />
                );

            case 7:
                return (
                    <Step7
                        data={wizard.data}
                    />
                );

            default:
                return null;

        }

    }

    return (

        <div className={styles.wizard}>

            <WizardSidebar
                currentStep={wizard.step}
                onStepSelect={(step) =>
                    setWizard((prev) => ({
                        ...prev,
                        step,
                    }))
                }
            />

            <main className={styles.main}>

                <WizardHeader

                    currentStep={wizard.step}

                    totalSteps={totalSteps}

                    onNext={nextStep}

                    onBack={previousStep}

                />

                {renderStep()}

                {wizard.step === totalSteps && (
                    <div className={styles.brainStatus}>
                        {brainStatus === null && (
                            <span>Checking connection to ReTour Brain...</span>
                        )}
                        {brainStatus?.api === "ok" && brainStatus.llm === "ok" && (
                            <span className={styles.brainOk}>
                                Connected to Brain · {brainStatus.model ?? "LLM ready"}
                            </span>
                        )}
                        {brainStatus?.api === "ok" && brainStatus.llm !== "ok" && (
                            <span className={styles.brainWarn}>
                                API online — LLM not ready. Run Ollama first.
                            </span>
                        )}
                        {brainStatus?.api === "down" && (
                            <span className={styles.brainError}>
                                Brain API offline — start backend on port 8000
                            </span>
                        )}
                    </div>
                )}

                {isGenerating && wizard.step === totalSteps ? (
                    <GenerationProgress
                        stage={brainStage}
                        label={brainStageLabel}
                        elapsedSec={elapsedSec}
                    />
                ) : null}

                {(packageResult || generateError) && wizard.step === totalSteps && (
                    <>
                        {generateError ? (
                            <div className={styles.jsonPanel}>
                                <p className={styles.jsonError}>{generateError}</p>
                            </div>
                        ) : (
                            <PackageExperience result={packageResult} />
                        )}
                        {!generateError && packageResult ? (
                            <RagKnowledgePanel result={packageResult} />
                        ) : null}
                    </>
                )}

                <div className={styles.actions}>

                    <button
                        className="btn btn-outline-secondary"
                        onClick={previousStep}
                        disabled={wizard.step === 1 || isGenerating}
                    >
                        Back
                    </button>

                    <button
                        className="btn btn-success"
                        onClick={handleContinue}
                        disabled={isGenerating}
                    >
                        {
                            isGenerating
                                ? `Generating... ${elapsedSec}s — do not click again`
                                : wizard.step === totalSteps
                                  ? "Generate My Package"
                                  : "Continue"
                        }
                    </button>

                </div>

            </main>

        </div>

    );

}