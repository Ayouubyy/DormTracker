from unittest.mock import patch

from link_watch import WATCHED_POSTS, is_any_registration_link_active, is_registration_link_active


def test_inactive_when_placeholder_has_no_anchor_tag():
    # Real markup captured from https://www.supcom.tn/details_actualite/136 (2026/2027,
    # not yet open): the "الرابط" right after "احترام مواعيد التسجيل" is plain text.
    html = (
        'بكل دقة</span> (مع احترام مواعيد التسجيل : الرابط). &nbsp;<span>'
        'يحتوي الرابط على التسجيل للراغبين في التمتع بالسكن الجامعي'
        '</span>'
    )
    assert is_registration_link_active(html, "احترام مواعيد التسجيل", "الرابط") is False


def test_active_when_placeholder_is_wrapped_in_a_real_anchor():
    # Real markup captured from https://www.supcom.tn/details_actualite/90 (last year's
    # equivalent Arabic post, after registration opened): the same placeholder is a real
    # link.
    html = (
        'بكل دقة</span> (مع احترام مواعيد التسجيل : '
        '<a href="https://edx.supcom.tn/public/short.faces?l=KULTsN">الرابط</a>). &nbsp;'
    )
    assert is_registration_link_active(html, "احترام مواعيد التسجيل", "الرابط") is True


def test_inactive_when_watch_phrase_is_missing_entirely():
    assert is_registration_link_active("nothing relevant here", "احترام مواعيد التسجيل", "الرابط") is False


def test_french_inactive_when_placeholder_has_no_anchor_tag():
    # Real markup captured from https://www.supcom.tn/details_actualite/138 (the French
    # counterpart of post 136, same announcement, not yet open): "lien" is plain text.
    html = (
        "ec le plus grand soin</span> (dans le respect des délais d'inscription : lien). "
        "<span>Ce même lien permet également aux étudiants...</span>"
    )
    assert is_registration_link_active(html, "délais d'inscription", "lien") is False


def test_french_active_when_placeholder_is_wrapped_in_a_real_anchor():
    html = (
        "ec le plus grand soin</span> (dans le respect des délais d'inscription : "
        '<a href="https://edx.supcom.tn/public/short.faces?l=X">lien</a>). '
    )
    assert is_registration_link_active(html, "délais d'inscription", "lien") is True


def test_watched_posts_covers_both_the_arabic_and_french_announcement():
    urls = {post["url"] for post in WATCHED_POSTS}
    assert urls == {
        "https://www.supcom.tn/details_actualite/136",
        "https://www.supcom.tn/details_actualite/138",
    }


@patch("link_watch.fetch_watched_post_html")
def test_is_any_registration_link_active_false_when_both_inactive(mock_fetch):
    mock_fetch.side_effect = lambda url: {
        "https://www.supcom.tn/details_actualite/136": "احترام مواعيد التسجيل : الرابط)",
        "https://www.supcom.tn/details_actualite/138": "délais d'inscription : lien)",
    }[url]

    assert is_any_registration_link_active() is False


@patch("link_watch.fetch_watched_post_html")
def test_is_any_registration_link_active_true_when_only_arabic_post_activated(mock_fetch):
    mock_fetch.side_effect = lambda url: {
        "https://www.supcom.tn/details_actualite/136": (
            'احترام مواعيد التسجيل : <a href="https://edx.supcom.tn/x">الرابط</a>)'
        ),
        "https://www.supcom.tn/details_actualite/138": "délais d'inscription : lien)",
    }[url]

    assert is_any_registration_link_active() is True


@patch("link_watch.fetch_watched_post_html")
def test_is_any_registration_link_active_true_when_only_french_post_activated(mock_fetch):
    mock_fetch.side_effect = lambda url: {
        "https://www.supcom.tn/details_actualite/136": "احترام مواعيد التسجيل : الرابط)",
        "https://www.supcom.tn/details_actualite/138": (
            'délais d\'inscription : <a href="https://edx.supcom.tn/x">lien</a>)'
        ),
    }[url]

    assert is_any_registration_link_active() is True
