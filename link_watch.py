import re

import requests

WATCHED_POST_URL = "https://www.supcom.tn/details_actualite/136"

# Every year's registration announcement repeats this exact phrase, immediately followed
# by a placeholder labeled "الرابط" ("the link") that SUP'COM leaves as plain text until
# registration (including housing) actually opens, at which point they wrap it in a real
# <a href> pointing at their edx.supcom.tn registration portal. Confirmed against last
# year's post (id 90, link was live) vs this year's post (id 136, still plain text).
LINK_WATCH_PHRASE = "احترام مواعيد التسجيل"

_ACTIVE_LINK_PATTERN = re.compile(r"<a\b[^>]*>\s*الرابط\s*</a>")


def fetch_watched_post_html(url: str = WATCHED_POST_URL, timeout: int = 15) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def is_registration_link_active(html: str) -> bool:
    idx = html.find(LINK_WATCH_PHRASE)
    if idx == -1:
        return False
    window = html[idx : idx + 300]
    return bool(_ACTIVE_LINK_PATTERN.search(window))
