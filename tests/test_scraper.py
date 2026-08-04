from pathlib import Path

from scraper import parse_latest_posts, Post

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_latest_posts_extracts_id_title_url():
    html = (FIXTURES / "homepage_sample.html").read_text(encoding="utf-8")

    posts = parse_latest_posts(html)

    assert posts == [
        Post(
            id=139,
            title="Appel à candidature pour le recrutement d'un(e) chercheur(se) Post-Doc 2026/2027",
            url="https://www.supcom.tn/details_actualite/139",
        ),
        Post(
            id=138,
            title="Avis concernant l'inscription universitaire et l'hébergement pour l'année universitaire 2026/2027",
            url="https://www.supcom.tn/details_actualite/138",
        ),
        Post(
            id=136,
            title="2027/2026 بلاغ حول التسجيل الجامعي وبالمبيت بعنوان السنة الجامعية",
            url="https://www.supcom.tn/details_actualite/136",
        ),
    ]


def test_parse_latest_posts_returns_empty_list_for_no_matches():
    assert parse_latest_posts("<html><body>nothing here</body></html>") == []
