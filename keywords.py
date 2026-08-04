HOUSING_KEYWORDS = [
    "hébergement",
    "hebergement",
    "logement",
    "cité universitaire",
    "cite universitaire",
    "résidence",
    "residence",
    "internat",
    "chambre",
    "سكن",
    "مبيت",
    "الإقامة",
    "دار الطالب",
]


def is_housing_related(title: str) -> bool:
    lowered = title.lower()
    return any(keyword.lower() in lowered for keyword in HOUSING_KEYWORDS)
