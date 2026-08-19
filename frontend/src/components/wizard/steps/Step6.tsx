"use client";

import { WizardData } from "@/types/wizard";

type Props = {

    data: WizardData;

    updateField: <K extends keyof WizardData>(
        field: K,
        value: WizardData[K]
    ) => void;

};

export default function Step6({

    data,

    updateField,

}: Props) {

    return (

        <>

            <div className="row">

                <div className="col-12">

                    <label className="form-label">

                        Tell ReTour AI More About Your Trip

                    </label>

                    <textarea

                        rows={8}

                        className="form-control"

                        placeholder="Example: We love nature, local food, photography, sunsets and would like to avoid crowded places..."

                        value={data.freeText}

                        onChange={(e) =>

                            updateField(

                                "freeText",

                                e.target.value

                            )

                        }

                    />

                </div>

                <div className="col-12 mt-4">

                    <div className="alert alert-success">

                        <strong>Tip:</strong> The more information you provide, the better the AI can personalize your itinerary.

                    </div>

                </div>

            </div>

        </>

    );

}