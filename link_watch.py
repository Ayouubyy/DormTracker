import re

import requests

# SUP'COM publishes the same registration announcement as two separate posts, one per
# language. Each repeats a fixed phrase immediately followed by a placeholder word
# ("the link") that stays plain text until registration (including housing) actually
# opens, at which point SUP'COM wraps it in a real <a href> pointing at their
# edx.supcom.tn registration portal — confirmed against last year's Arabic post (id 90,
# link was live) vs this year's Arabic (id 136) and French (id 138) posts, both still
# plain text as of this writing. Either post activating is the same real-world event, so
# a single check watches both and treats either one going live as the signal.
WATCHED_POSTS = [
    {
        "url": "https://www.supcom.tn/details_actualite/136",
        "phrase": "احترام مواعيد التسجيل",
        "placeholder": "الرابط",
    },
    {
        "url": "https://www.supcom.tn/details_actualite/138",
        "phrase": "délais d'inscription",
        "placeholder": "lien",
    },
]


def fetch_watched_post_html(url: str, timeout: int = 15) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def is_registration_link_active(html: str, phrase: str, placeholder: str) -> bool:
    idx = html.find(phrase)
    if idx == -1:
        return False
    window = html[idx : idx + 300]
    pattern = re.compile(rf"<a\b[^>]*>\s*{re.escape(placeholder)}\s*</a>")
    return bool(pattern.search(window))


def is_any_registration_link_active() -> bool:
    return any(
        is_registration_link_active(
            fetch_watched_post_html(post["url"]), post["phrase"], post["placeholder"]
        )
        for post in WATCHED_POSTS
    )
