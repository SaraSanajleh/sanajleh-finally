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

const groupTypes = [

    "solo",

    "couple",

    "family",

    "friends",

    "business",

];

const accessibility = [

    "Wheelchair",

    "Limited Walking",

    "Visual",

    "Hearing",

    "Elder Friendly",

];

export default function Step2({

    data,

    updateField,

}: Props) {

    return (

        <>

            <div className="row g-4">

                <div className="col-md-3">

                    <label className="form-label">

                        Adults

                    </label>

                    <input

                        type="number"

                        min={1}

                        className="form-control"

                        value={data.adults}

                        onChange={(e) =>

                            updateField(

                                "adults",

                                Number(e.target.value)

                            )

                        }

                    />

                </div>

                <div className="col-md-3">

                    <label className="form-label">

                        Children

                    </label>

                    <input

                        type="number"

                        min={0}

                        className="form-control"

                        value={data.children}

                        onChange={(e) =>

                            updateField(

                                "children",

                                Number(e.target.value)

                            )

                        }

                    />

                </div>

                <div className="col-md-3">

                    <label className="form-label">

                        Seniors

                    </label>

                    <input

                        type="number"

                        min={0}

                        className="form-control"

                        value={data.seniors}

                        onChange={(e) =>

                            updateField(

                                "seniors",

                                Number(e.target.value)

                            )

                        }

                    />

                </div>

                <div className="col-md-3">

                    <label className="form-label">

                        Group Type

                    </label>

                    <select

                        className="form-select"

                        value={data.groupType}

                        onChange={(e) =>

                            updateField(

                                "groupType",

                                e.target.value as any

                            )

                        }

                    >

                        <option value="">

                            Select

                        </option>

                        {

                            groupTypes.map((type) => (

                                <option

                                    key={type}

                                    value={type}

                                >

                                    {

                                        type.charAt(0).toUpperCase() +

                                        type.slice(1)

                                    }

                                </option>

                            ))

                        }

                    </select>

                </div>

                {

                    data.children > 0 && (

                        <div className="col-12">

                            <label className="form-label">

                                Children Ages

                            </label>

                            <div className="row g-3">

                                {

                                    Array.from({

                                        length: data.children

                                    }).map((_, index) => (

                                        <div

                                            key={index}

                                            className="col-md-2"

                                        >

                                            <input

                                                type="number"

                                                min={0}

                                                max={17}

                                                className="form-control"

                                                placeholder={`Child ${index + 1}`}

                                                value={

                                                    data.childrenAges[index] || ""

                                                }

                                                onChange={(e) => {

                                                    const ages = [

                                                        ...data.childrenAges,

                                                    ];

                                                    ages[index] =

                                                        e.target.value;

                                                    updateField(

                                                        "childrenAges",

                                                        ages

                                                    );

                                                }}

                                            />

                                        </div>

                                    ))

                                }

                            </div>

                        </div>

                    )

                }

                <div className="col-12">

                    <label className="form-label">

                        Accessibility Needs

                    </label>

                    <div className={styles.regionChips}>

                        {

                            accessibility.map((item) => {

                                const selected =

                                    data.accessibilityNeeds.includes(item);

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

                                                    "accessibilityNeeds",

                                                    data.accessibilityNeeds.filter(

                                                        x => x !== item

                                                    )

                                                );

                                            } else {

                                                updateField(

                                                    "accessibilityNeeds",

                                                    [

                                                        ...data.accessibilityNeeds,

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

            </div>

        </>

    );

}