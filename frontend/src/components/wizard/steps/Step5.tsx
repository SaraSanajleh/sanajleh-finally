"use client";

import { WizardData, PriorityId } from "@/types/wizard";

import styles from "@/styles/wizard/wizard.module.css";

type Props = {

    data: WizardData;

    updateField: <K extends keyof WizardData>(
        field: K,
        value: WizardData[K]
    ) => void;

};

const priorities: {

    id: PriorityId;

    title: string;

    description: string;

}[] = [

        {
            id: "budget",
            title: "Budget",
            description: "Keep costs low",
        },

        {
            id: "comfort",
            title: "Comfort",
            description: "Premium experience",
        },

        {
            id: "famous",
            title: "Top Attractions",
            description: "Must-see places",
        },

        {
            id: "hidden",
            title: "Hidden Gems",
            description: "Less crowded places",
        },

        {
            id: "authentic",
            title: "Authentic",
            description: "Local experiences",
        },

        {
            id: "family",
            title: "Family",
            description: "Kid friendly",
        },

        {
            id: "maximize",
            title: "Maximize",
            description: "See as much as possible",
        },

        {
            id: "sustainable",
            title: "Eco Tourism",
            description: "Sustainable choices",
        },

    ];

export default function Step5({

    data,

    updateField,

}: Props) {

    return (

        <>

            <div className="row g-3">

                {

                    priorities.map((priority) => (

                        <div

                            key={priority.id}

                            className="col-lg-6"

                        >

                            <button

                                type="button"

                                className={`${styles.priorityOption}

                                ${data.aiPriority === priority.id

                                        ? styles.priorityActive

                                        : ""

                                    }`}

                                onClick={() =>

                                    updateField(

                                        "aiPriority",

                                        priority.id

                                    )

                                }

                            >

                                <h6>

                                    {priority.title}

                                </h6>

                                <small>

                                    {priority.description}

                                </small>

                            </button>

                        </div>

                    ))

                }

            </div>

        </>

    );

}