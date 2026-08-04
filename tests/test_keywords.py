from keywords import is_housing_related


def test_matches_french_hebergement_with_accent():
    title = "Avis concernant l'inscription universitaire et l'hébergement pour l'année universitaire 2026/2027"
    assert is_housing_related(title) is True


def test_matches_arabic_mabit():
    title = "2027/2026 بلاغ حول التسجيل الجامعي وبالمبيت بعنوان السنة الجامعية"
    assert is_housing_related(title) is True


def test_matches_is_case_insensitive():
    assert is_housing_related("HÉBERGEMENT étudiant ouvert") is True


def test_does_not_match_unrelated_title():
    title = "Fierté et Excellence : Enactus SUP'COM est Champion de Tunisie !"
    assert is_housing_related(title) is False
