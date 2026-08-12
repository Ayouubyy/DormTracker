import requests

# Tunisia's national university registration portal — down for maintenance behind an
# HTTP Basic Auth gate (confirmed: 401 + WWW-Authenticate: BASIC) as of this writing.
# It coming back online is a strong signal registration season is starting nationally.
INSCRIPTION_URL = "https://www.inscription.tn/"


def is_site_up(url: str, timeout: int = 15) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return False
    return response.status_code < 400
