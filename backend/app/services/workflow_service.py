ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"analyzed", "withdrawn"},
    "analyzed": {"shortlisted", "rejected", "withdrawn"},
    "shortlisted": {"interview_proposed", "withdrawn"},
    "interview_proposed": {"interviewed", "withdrawn"},
    "interviewed": {"hire_approved", "rejected", "withdrawn"},
    "hire_approved": {"offer_drafted", "withdrawn"},
    "offer_drafted": {"offer_approved", "hire_approved", "withdrawn"},
    "offer_approved": {"offer_accepted", "offer_drafted", "withdrawn"},  # offer_drafted = revised offer
    "offer_accepted": {"documents_pending", "withdrawn"},
    "documents_pending": {"documents_complete", "withdrawn"},
    "documents_complete": {"joining_letter_approved", "withdrawn"},
    "joining_letter_approved": {"contract_received", "withdrawn"},
    "contract_received": {"joined", "withdrawn"},
    "rejected": set(), "joined": set(), "withdrawn": set(),
}