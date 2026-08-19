# SME intelligence

ReTour recommends local tourism businesses so SMEs can grow. Recommendations must feel like part of the trip, not ads.

## Package rule

A package gets **one tour guide** and **one tour operator** for the whole journey.

Not a different SME on every day. Travelers hire a team for the trip, not a new face at breakfast.

## What the traveler sees

Each recommended guide or operator shows:

- What they are distinguished by (`known_for`)
- Specs from the record: languages, group size, pricing, hours, rating
- Which itinerary regions they actually cover
- Why they matched this traveler and this route

## Matching

Candidates are scored against the **full trip**:

- How much of the locked route they cover (must-visit regions weigh more)
- Specializations vs traveler interests
- Target customer types vs group type
- Languages and group capacity
- Operators with transport score higher on multi-region trips
- Optional subscription boost only after a relevance threshold

Women-led and similar labels are never inferred.

## Fairness

`tourist relevance > business promotion`

An irrelevant subscribed SME is not inserted.
