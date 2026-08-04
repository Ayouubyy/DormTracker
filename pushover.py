import requests

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"


class PushoverError(RuntimeError):
    pass


def send_pushover(
    user_key: str,
    api_token: str,
    message: str,
    title: str | None = None,
    priority: int = 0,
    sound: str | None = None,
    retry: int | None = None,
    expire: int | None = None,
    timeout: int = 15,
) -> dict:
    payload = {
        "token": api_token,
        "user": user_key,
        "message": message,
        "priority": priority,
    }
    if title is not None:
        payload["title"] = title
    if sound is not None:
        payload["sound"] = sound
    if priority == 2:
        payload["retry"] = retry if retry is not None else 60
        payload["expire"] = expire if expire is not None else 10800

    response = requests.post(PUSHOVER_API_URL, data=payload, timeout=timeout)
    if response.status_code != 200:
        raise PushoverError(f"Pushover API returned {response.status_code}: {response.text}")

    return response.json()
