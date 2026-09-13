"""Canned MockProvider responses for the 12 sample emails, keyed by prompt
name, in the order the worker processes the files (sorted by filename).

Used by tests and by the offline demo mode (LLM_PROVIDER_ORDER=mock), so
`make demo` works with zero API keys."""


def canned_responses() -> dict:
    return {
        # one classification per sample file, in sorted-filename order
        "classify": [
            {"category": "lead", "confidence": 0.95},  # 01-lead-sarah
            {"category": "lead", "confidence": 0.92},  # 02-lead-michael
            {"category": "document", "confidence": 0.90},  # 03-doc-riverside
            {"category": "lead", "confidence": 0.90},  # 04-lead-phone-typo
            {"category": "document", "confidence": 0.93},  # 05-doc-oakwood
            {"category": "status_update", "confidence": 0.90},  # 06-status-inspection
            {"category": "document", "confidence": 0.91},  # 07-doc-pinehill-baddates
            {"category": "other", "confidence": 0.90},  # 08-other-newsletter
            {"category": "lead", "confidence": 0.88},  # 09-lead-fatima
            {"category": "status_update", "confidence": 0.92},  # 10-status-funds
            {"category": "other", "confidence": 0.95},  # 11-other-vendor
            {"category": "lead", "confidence": 0.55},  # 12-lead-ambiguous
        ],
        # one per lead email, in order: 01, 02, 04, 09, 12
        "extract_lead": [
            {
                "name": "Sarah Chen",
                "email": "sarah.chen@example.com",
                "phone": "+1 415 555 0182",
                "reference": "RIV-2031",
                "intent": "Wants details and a morning viewing of listing RIV-2031",
            },
            {
                "name": "Michael Okafor",
                "email": "m.okafor@example.com",
                "phone": "+44 20 7946 0958",
                "reference": None,
                "intent": "Relocating; wants to view three-bedroom houses on Saturday",
            },
            {
                "name": "Daniel Reyes",
                "email": "daniel.reyes@example.com",
                "phone": "5551-02",
                "reference": None,
                "intent": "Thinking of selling his duplex, wants a callback",
            },
            {
                "name": "Fatima Al-Rashid",
                "email": "fatima.rashid@example.com",
                "phone": "+971 50 123 4567",
                "reference": "MAP-3307",
                "intent": "Budget confirmed, ready to make an offer on MAP-3307",
            },
            {
                "name": "J.",
                "email": "j.h.2211@example.com",
                "phone": None,
                "reference": None,
                "intent": "Vague interest in moving or selling, no specifics",
            },
        ],
        # one per document email, in order: 03, 05, 07
        "extract_document": [
            {
                "parties": ["Riverside Holdings LLC", "Chen Family Trust"],
                "amounts": [450000.0, 5000.0],
                "key_dates": {
                    "acceptance": "2026-09-01",
                    "earnest_money": "2026-09-04",
                    "due_diligence": "2026-09-15",
                    "closing": "2026-10-01",
                },
                "reference": "RIV-2031",
            },
            {
                "parties": ["Oakwood Ventures LP", "Gonzalez Properties Inc"],
                "amounts": [275000.0],
                "key_dates": {
                    "acceptance": "2026-08-20",
                    "earnest_money": "2026-08-24",
                    "due_diligence": "2026-09-05",
                    "closing": "2026-09-30",
                },
                "reference": "OAK-1189",
            },
            {
                "parties": ["Pine Hill Group", "Marsh & Sons LLC"],
                "amounts": [1250000.0],
                "key_dates": {
                    "acceptance": "2026-10-01",
                    "earnest_money": "2026-10-05",
                    "due_diligence": "2026-09-20",
                    "closing": "2026-09-05",
                },
                "reference": "PIN-7742",
            },
        ],
    }
