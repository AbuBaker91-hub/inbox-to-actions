<!--
Schema (LeadRecord):
{
  "name": string | null,       full name of the person
  "email": string | null,      their email address
  "phone": string | null,      phone number exactly as written
  "reference": string | null,  listing/deal reference code (e.g. RIV-2031)
  "intent": string | null      one sentence: what they want
}
-->
Extract the lead's contact details from the email below.

Rules:
- Use only values present in the text. If a field is not present, return null.
- Never invent, complete or "fix" values. Copy the phone number exactly as it
  appears, even if it looks wrong — validation happens downstream.
- "email" is the lead's own address (usually the From address unless the body
  says otherwise).
- "reference" is a listing or deal code if one is mentioned, else null.

Email:
{{email}}

Respond with only the JSON object, no prose, no markdown fences.
