# Prompts

Prompts are assembled by `PromptBuilder`. They are not one giant uncontrolled string.

## Sections

`prompts/v2/system.md` — role and hard rules  
`prompts/v2/planning_rules.md` — planning process  
`prompts/v2/output_contract.md` — JSON contract  

The user message then appends isolated JSON objects:

- Wizard request
- Tourist profile
- Planning context
- Retrieved POIs / restaurants / hotels
- Trip SME team (one guide + one operator)
- Output instruction

## Rules the model is told

- Never invent catalog or SME entities
- Use retrieved IDs only
- Honor must-visit and places-to-avoid
- Keep days geographically coherent
- Recommend SMEs only when relevant
- Return valid JSON

Internal prompts are not shown in the public itinerary UI. Case capture stores inputs, retrieval, and output for debugging.
