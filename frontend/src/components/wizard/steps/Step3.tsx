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

const interests = [

    "History",
    "Culture",
    "Nature",
    "Adventure",
    "Food",
    "Photography",
    "Shopping",
    "Museums",
    "Camping",
    "Hiking",
    "Luxury",
    "Wellness",
    "Local Experiences",
    "Religious Sites",

];

const mustVisit = [

    "Petra",
    "Wadi Rum",
    "Dead Sea",
    "Amman",
    "Jerash",
    "Aqaba",

];

export default function Step3({

    data,

    updateField,

}: Props) {

    return (

        <>

            <div className="row g-4">

                <div className="col-md-6">

                    <label className="form-label">

                        Trip Pace

                    </label>

                    <select

                        className="form-select"

                        value={data.tripPace}

                        onChange={(e) =>

                            updateField(

                                "tripPace",

                                e.target.value

                            )

                        }

                    >

                        <option value="">

                            Select

                        </option>

                        <option>

                            Relaxed

                        </option>

                        <option>

                            Balanced

                        </option>

                        <option>

                            Fast

                        </option>

                    </select>

                </div>

                <div className="col-md-6">

                    <label className="form-label">

                        Activity Level

                    </label>

                    <select

                        className="form-select"

                        value={data.activityLevel}

                        onChange={(e) =>

                            updateField(

                                "activityLevel",

                                e.target.value

                            )

                        }

                    >

                        <option value="">

                            Select

                        </option>

                        <option>

                            Easy

                        </option>

                        <option>

                            Moderate

                        </option>

                        <option>

                            Active

                        </option>

                    </select>

                </div>

                <div className="col-12">

                    <label className="form-label">

                        Interests

                    </label>

                    <div className={styles.regionChips}>

                        {

                            interests.map((item) => {

                                const selected =

                                    data.interests.includes(item);

                                return (

                                    <button

                                        key={item}

                                        type="button"

                                        className={`${styles.regionChip}

                                        ${selected

                                                ? styles.activeRegion

                                                : ""

                                            }`}

                                        onClick={() => {

                                            if (selected) {

                                                updateField(

                                                    "interests",

                                                    data.interests.filter(

                                                        x => x !== item

                                                    )

                                                );

                                            }

                                            else {

                                                updateField(

                                                    "interests",

                                                    [

                                                        ...data.interests,

                                                        item,

                                                    ]

                                                );

                                            }

                                        }}

                                    >

                                        {item}

                                    </button>

                                );

                            })

                        }

                    </div>

                </div>

                <div className="col-12">

                    <label className="form-label">

                        Must Visit

                    </label>

                    <div className={styles.regionChips}>

                        {

                            mustVisit.map((place) => {

                                const selected =

                                    data.mustVisit.includes(place);

                                return (

                                    <button

                                        key={place}

                                        type="button"

                                        className={`${styles.regionChip}

                                        ${selected

                                                ? styles.activeRegion

                                                : ""

                                            }`}

                                        onClick={() => {

                                            if (selected) {

                                                updateField(

                                                    "mustVisit",

                                                    data.mustVisit.filter(

                                                        x => x !== place

                                                    )

                                                );

                                            }

                                            else {

                                                updateField(

                                                    "mustVisit",

                                                    [

                                                        ...data.mustVisit,

                                                        place,

                                                    ]

                                                );

                                            }

                                        }}

                                    >

                                        {place}

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