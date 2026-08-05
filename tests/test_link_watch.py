from link_watch import is_registration_link_active


def test_inactive_when_placeholder_has_no_anchor_tag():
    # Real markup captured from https://www.supcom.tn/details_actualite/136 (2026/2027,
    # not yet open): the "الرابط" right after "احترام مواعيد التسجيل" is plain text.
    html = (
        'بكل دقة</span> (مع احترام مواعيد التسجيل : الرابط). &nbsp;<span>'
        'يحتوي الرابط على التسجيل للراغبين في التمتع بالسكن الجامعي'
        '</span>'
    )
    assert is_registration_link_active(html) is False


def test_active_when_placeholder_is_wrapped_in_a_real_anchor():
    # Real markup captured from https://www.supcom.tn/details_actualite/90 (last year's
    # equivalent post, after registration opened): the same placeholder is a real link.
    html = (
        'بكل دقة</span> (مع احترام مواعيد التسجيل : '
        '<a href="https://edx.supcom.tn/public/short.faces?l=KULTsN">الرابط</a>). &nbsp;'
    )
    assert is_registration_link_active(html) is True


def test_inactive_when_watch_phrase_is_missing_entirely():
    assert is_registration_link_active("<html><body>nothing relevant here</body></html>") is False
