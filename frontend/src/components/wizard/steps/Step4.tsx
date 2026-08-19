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

const cuisines = [

    "Jordanian",
    "Arabic",
    "Italian",
    "Seafood",
    "BBQ",
    "Vegetarian",
    "Vegan",
    "Fast Food",
    "Desserts",

];

const smeOptions = [

    "Family-owned",
    "Eco-friendly",
    "Women-led",
    "Community-based",
    "Luxury",

];

export default function Step4({

    data,

    updateField,

}: Props) {

    return (

        <>

            <div className="row g-4">

                <div className="col-md-6">

                    <label className="form-label">

                        Accommodation

                    </label>

                    <select

                        className="form-select"

                        value={data.accommodationType}

                        onChange={(e) =>

                            updateField(

                                "accommodationType",

                                e.target.value as any

                            )

                        }

                    >

                        <option value="">

                            Select

                        </option>

                        <option value="hotel">

                            Hotel

                        </option>

                        <option value="resort">

                            Resort

                        </option>

                        <option value="boutique">

                            Boutique Hotel

                        </option>

                        <option value="eco_lodge">

                            Eco Lodge

                        </option>

                        <option value="desert_camp">

                            Desert Camp

                        </option>

                        <option value="no_pref">

                            No Preference

                        </option>

                    </select>

                </div>

                <div className="col-md-6">

                    <label className="form-label">

                        Hotel Rating

                    </label>

                    <select

                        className="form-select"

                        value={data.hotelRating}

                        onChange={(e) =>

                            updateField(

                                "hotelRating",

                                e.target.value

                            )

                        }

                    >

                        <option value="">

                            Select

                        </option>

                        <option>

                            3 Stars

                        </option>

                        <option>

                            4 Stars

                        </option>

                        <option>

                            5 Stars

                        </option>

                        <option>

                            No Preference

                        </option>

                    </select>

                </div>

                <div className="col-12">

                    <label className="form-label">

                        Cuisine Preferences

                    </label>

                    <div className={styles.regionChips}>

                        {

                            cuisines.map((item) => {

                                const selected =

                                    data.cuisine.includes(item);

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

                                                    "cuisine",

                                                    data.cuisine.filter(

                                                        x => x !== item

                                                    )

                                                );

                                            } else {

                                                updateField(

                                                    "cuisine",

                                                    [

                                                        ...data.cuisine,

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

                <div className="col-md-6">

                    <label className="form-label">

                        Special Occasion

                    </label>

                    <select

                        className="form-select"

                        value={data.specialOccasion}

                        onChange={(e) =>

                            updateField(

                                "specialOccasion",

                                e.target.value

                            )

                        }

                    >

                        <option value="">

                            None

                        </option>

                        <option>

                            Birthday

                        </option>

                        <option>

                            Honeymoon

                        </option>

                        <option>

                            Anniversary

                        </option>

                        <option>

                            Graduation

                        </option>

                    </select>

                </div>

                <div className="col-md-6">

                    <label className="form-label">

                        Places To Avoid

                    </label>

                    <input

                        className="form-control"

                        placeholder="Optional"

                        value={data.placesToAvoid}

                        onChange={(e) =>

                            updateField(

                                "placesToAvoid",

                                e.target.value

                            )

                        }

                    />

                </div>

                <div className="col-12">

                    <label className="form-label">

                        SME Preferences

                    </label>

                    <div className={styles.regionChips}>

                        {

                            smeOptions.map((item) => {

                                const selected =

                                    data.smePreferences.includes(item);

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

                                                    "smePreferences",

                                                    data.smePreferences.filter(

                                                        x => x !== item

                                                    )

                                                );

                                            } else {

                                                updateField(

                                                    "smePreferences",

                                                    [

                                                        ...data.smePreferences,

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