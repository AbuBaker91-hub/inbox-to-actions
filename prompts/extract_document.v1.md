<!--
Schema (DocumentRecord):
{
  "parties": [string, ...],    the named parties to the agreement, in order
  "amounts": [number, ...],    monetary amounts in the document (largest first)
  "key_dates": {
    "acceptance":    "YYYY-MM-DD" | null,
    "earnest_money": "YYYY-MM-DD" | null,
    "due_diligence": "YYYY-MM-DD" | null,
    "closing":       "YYYY-MM-DD" | null
  },
  "reference": string | null   the agreement's reference code
}
-->
Extract the agreement details from the email and its attached document text.

Rules:
- Use only values present in the text. If a field is not present, return null
  (or an empty list). Never invent or infer values.
- Dates must be ISO format YYYY-MM-DD. Copy the dates as stated even if their
  order looks wrong — validation happens downstream.
- "amounts" are plain numbers without currency symbols, largest first.
- "reference" is the agreement or deal code if stated, else null.

Email:
{{email}}

Attached document text:
{{attachment_text}}

Respond with only the JSON object, no prose, no markdown fences.
