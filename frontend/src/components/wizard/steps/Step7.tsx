"use client";

import { WizardData } from "@/types/wizard";

import styles from "@/styles/wizard/wizard.module.css";

type Props = {

    data: WizardData;

};

export default function Step7({

    data,

}: Props) {

    return (

        <>

            <div className="row g-4">

                <div className="col-md-6">

                    <div className={styles.summaryBox}>

                        <h5>

                            Trip

                        </h5>

                        <p>

                            <strong>Date:</strong> {data.startDate || "-"}

                        </p>

                        <p>

                            <strong>Duration:</strong> {data.duration}

                        </p>

                        <p>

                            <strong>Airport:</strong> {data.arrivalAirport || "-"}
                            {data.arrivalTime ? ` at ${data.arrivalTime}` : ""}

                        </p>

                        <p>

                            <strong>Budget:</strong> {data.totalBudget || "-"}

                        </p>

                    </div>

                </div>

                <div className="col-md-6">

                    <div className={styles.summaryBox}>

                        <h5>

                            Travelers

                        </h5>

                        <p>

                            Adults: {data.adults}

                        </p>

                        <p>

                            Children: {data.children}

                        </p>

                        <p>

                            Seniors: {data.seniors}

                        </p>

                        <p>

                            Group: {data.groupType || "-"}

                        </p>

                    </div>

                </div>

                <div className="col-12">

                    <div className={styles.summaryBox}>

                        <h5>

                            AI Preferences

                        </h5>

                        <p>

                            Priority: {data.aiPriority || "-"}

                        </p>

                        <p>

                            Accommodation: {data.accommodationType || "-"}

                        </p>

                        <p>

                            Hotel Rating: {data.hotelRating || "-"}

                        </p>

                        <p>

                            Special Occasion: {data.specialOccasion || "-"}

                        </p>

                    </div>

                </div>

                <div className="col-12">

                    <div className={styles.summaryBox}>

                        <h5>

                            Additional Notes

                        </h5>

                        <p>

                            {

                                data.freeText ||

                                "No additional notes."

                            }

                        </p>

                    </div>

                </div>

            </div>

        </>

    );

}