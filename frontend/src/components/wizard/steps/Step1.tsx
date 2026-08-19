"use client";

import { WizardData } from "@/types/wizard";

import styles from "@/styles/wizard/wizard.module.css";

type Props = {

    data: WizardData;

    updateField: <K extends keyof WizardData>(
        field: K,
        value: WizardData[K]
    ) => void;

};

const durations = ["1", "2", "3", "5", "7", "Custom"];

const languages = [

    "English",

    "Arabic",

    "French",

    "German",

    "Spanish",

    "Italian",

];

const airports = [

    {
        value: "AMM",
        label: "Queen Alia International Airport (Amman)",
    },

    {
        value: "AQJ",
        label: "King Hussein International Airport (Aqaba)",
    },

    {
        value: "OTHER",
        label: "Other Airport",
    },

];

const regions = [

    "Amman",

    "Petra",

    "Wadi Rum",

    "Dead Sea",

    "Aqaba",

    "Jerash",

    "Ajloun",

    "Madaba",

];

export default function Step1({

    data,

    updateField,

}: Props) {

    return (

        <>

            <div className="row g-4">

                <div className="col-12">

                    <label className="form-label">

                        <i className="bi bi-calendar-event me-2 text-success"></i>
                        When are you planning to visit Jordan?

                    </label>

                    <input

                        type="date"

                        className="form-control"

                        value={data.startDate}

                        onChange={(e) =>

                            updateField(

                                "startDate",

                                e.target.value

                            )

                        }

                    />

                </div>

                <div className="col-md-6">

                    <label className="form-label">

                        <i className="bi bi-airplane me-2 text-success"></i>
                        Arrival Airport

                    </label>

                    <select

                        className="form-select"

                        value={data.arrivalAirport}

                        onChange={(e) =>

                            updateField(

                                "arrivalAirport",

                                e.target.value as any

                            )

                        }

                    >

                        <option value="">

                            Select Airport

                        </option>

                        {

                            airports.map((airport) => (

                                <option

                                    key={airport.value}

                                    value={airport.value}

                                >

                                    {airport.label}

                                </option>

                            ))

                        }

                    </select>

                </div>

                <div className="col-md-6">

                    <label className="form-label">

                        <i className="bi bi-clock me-2 text-success"></i>
                        Arrival time

                    </label>

                    <input

                        type="time"

                        className="form-control"

                        value={data.arrivalTime}

                        onChange={(e) =>

                            updateField(

                                "arrivalTime",

                                e.target.value

                            )

                        }

                    />

                    <p className={styles.fieldHint}>
                        Used to plan the first hours: early landings sleep then still get a light day; evening landings just rest.
                    </p>

                </div>

                <div className="col-12">

                    <label className="form-label">

                        <i className="bi bi-calendar-week me-2 text-success"></i>
                        Trip Duration

                    </label>

                    <div className={styles.durationButtons}>

                        {

                            durations.map((item) => (

                                <button
                                    key={item}
                                    type="button"
                                    className={`${styles.durationButton} ${data.duration === item
                                        ? styles.activeDuration
                                        : ""
                                        }`}
                                    onClick={() =>
                                        updateField(
                                            "duration",
                                            item as any
                                        )
                                    }
                                >
                                    {item === "Custom"
                                        ? "Custom"
                                        : `${item} Day`
                                    }
                                </button>

                            ))

                        }

                    </div>

                </div>
                <div className="col-md-6">

                    <label className="form-label">

                        <i className="bi bi-wallet2 me-2 text-success"></i>
                        Estimated Trip Budget

                    </label>

                    <input

                        type="number"

                        className="form-control"

                        placeholder="Example: 1,200 JOD"

                        value={data.totalBudget}

                        onChange={(e) =>

                            updateField(

                                "totalBudget",

                                e.target.value

                            )

                        }

                    />

                </div>

                <div className="col-md-6">

                    <label className="form-label">

                        <i className="bi bi-globe2 me-2 text-success"></i>
                        Preferred Language


                    </label>

                    <select

                        className="form-select"

                        value={data.preferredLanguage}

                        onChange={(e) =>

                            updateField(

                                "preferredLanguage",

                                e.target.value

                            )

                        }

                    >

                        {

                            languages.map((language) => (

                                <option

                                    key={language}

                                    value={language}

                                >

                                    {language}

                                </option>

                            ))

                        }

                    </select>

                </div>

                {

                    data.duration === "Custom" && (

                        <div className="col-md-6">

                            <label className="form-label">

                                Custom Duration

                            </label>

                            <input

                                className="form-control"

                                placeholder="Number of days"

                                value={data.customDuration}

                                onChange={(e) =>

                                    updateField(

                                        "customDuration",

                                        e.target.value

                                    )

                                }

                            />

                        </div>

                    )

                }

                <div className="col-12">

                    <label className="form-label">
                        <i className="bi bi-geo-alt me-2 text-success"></i>
                        Destinations to Explore
                    </label>

                    <p className={styles.fieldHint}>
                        Select one or more destinations.
                    </p>

                    <div className={styles.regionChips}>

                        {

                            regions.map((region) => {

                                const selected =

                                    data.preferredRegion.includes(region);

                                return (

                                    <button

                                        key={region}

                                        type="button"

                                        className={
                                            selected
                                                ? `${styles.regionChip} ${styles.activeRegion}`
                                                : styles.regionChip
                                        }

                                        onClick={() => {

                                            if (selected) {

                                                updateField(

                                                    "preferredRegion",

                                                    data.preferredRegion.filter(

                                                        item => item !== region

                                                    )

                                                );

                                            } else {

                                                updateField(

                                                    "preferredRegion",

                                                    [

                                                        ...data.preferredRegion,

                                                        region,

                                                    ]

                                                );

                                            }

                                        }}

                                    >

                                        {region}

                                    </button>

                                );

                            })

                        }

                    </div>

                </div>

            </div>

        </>

    );

}