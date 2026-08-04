import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

SUPCOM_URL = "https://www.supcom.tn/"

_ID_PATTERN = re.compile(r"/details_actualite/(\d+)")


@dataclass
class Post:
    id: int
    title: str
    url: str


def fetch_html(url: str = SUPCOM_URL, timeout: int = 15) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_latest_posts(html: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[Post] = []

    for item in soup.select("div.course-item"):
        link = item.select_one("h5.mb-3 a[href]")
        if link is None:
            continue

        href = link["href"]
        match = _ID_PATTERN.search(href)
        if not match:
            continue

        posts.append(
            Post(
                id=int(match.group(1)),
                title=link.get_text(strip=True),
                url=href,
            )
        )

    return posts
