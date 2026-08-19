import type { WizardData } from "@/types/wizard";

export function validateWizardStep(step: number, data: WizardData): string[] {
  const errors: string[] = [];

  switch (step) {
    case 1:
      if (!data.startDate.trim()) {
        errors.push("Visit date is required");
      }
      if (!data.arrivalAirport) {
        errors.push("Arrival airport is required");
      }
      if (!data.arrivalTime.trim()) {
        errors.push("Arrival time is required");
      }
      if (!data.totalBudget.trim() || Number(data.totalBudget) <= 0) {
        errors.push("Trip budget is required");
      }
      if (data.preferredRegion.length === 0) {
        errors.push("Select at least one destination");
      }
      if (
        data.duration === "Custom" &&
        (!data.customDuration.trim() || Number(data.customDuration) < 1)
      ) {
        errors.push("Custom duration (number of days) is required");
      }
      break;
    case 2:
      if (!data.groupType) {
        errors.push("Group type is required");
      }
      if (data.adults < 1) {
        errors.push("At least one adult is required");
      }
      break;
    case 3:
      if (data.interests.length === 0) {
        errors.push("Select at least one interest");
      }
      if (!data.tripPace) {
        errors.push("Trip pace is required");
      }
      if (!data.activityLevel) {
        errors.push("Activity level is required");
      }
      break;
    case 4:
      if (!data.accommodationType) {
        errors.push("Accommodation type is required");
      }
      if (!data.hotelRating) {
        errors.push("Hotel rating is required");
      }
      break;
    case 5:
      if (!data.aiPriority) {
        errors.push("Select what matters most for your trip");
      }
      break;
    default:
      break;
  }

  return errors;
}

export function validateWizardForGenerate(data: WizardData): string[] {
  const errors: string[] = [];
  for (let step = 1; step <= 5; step += 1) {
    errors.push(...validateWizardStep(step, data));
  }
  return errors;
}
