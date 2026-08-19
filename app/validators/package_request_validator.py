"""Additional business-rule validation for package requests."""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.schemas.request.package_request import PackageRequest


def validate_package_request(request: PackageRequest) -> PackageRequest:
    """
    Apply cross-field business rules beyond Pydantic schema validation.

    Pydantic handles field-level rules; this layer handles domain constraints.
    """
    total_people = request.travelers.adults + request.travelers.children + request.travelers.seniors
    if total_people > 20:
        raise ValidationError("Total travelers cannot exceed 20")

    if request.trip.totalBudget <= 0:
        raise ValidationError("totalBudget must be greater than zero for package generation")

    min_daily_budget = 30 * request.duration_days
    if request.trip.totalBudget < min_daily_budget:
        raise ValidationError(
            f"totalBudget ({request.trip.totalBudget} JOD) is unrealistically low "
            f"for a {request.duration_days}-day trip (minimum suggested: {min_daily_budget} JOD)"
        )

    return request
