from unittest.mock import patch, MagicMock

import pytest
import requests

from pushover import send_pushover, PushoverError, PUSHOVER_API_URL


@patch("pushover.requests.post")
def test_send_pushover_posts_expected_normal_priority_payload(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"status": 1})

    send_pushover("user123", "token456", message="hello", title="Hi")

    mock_post.assert_called_once_with(
        PUSHOVER_API_URL,
        data={
            "token": "token456",
            "user": "user123",
            "message": "hello",
            "priority": 0,
            "title": "Hi",
        },
        timeout=15,
    )


@patch("pushover.requests.post")
def test_send_pushover_emergency_priority_includes_retry_and_expire(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"status": 1})

    send_pushover(
        "user123", "token456", message="urgent", title="Alert",
        priority=2, sound="siren", retry=60, expire=10800,
    )

    mock_post.assert_called_once_with(
        PUSHOVER_API_URL,
        data={
            "token": "token456",
            "user": "user123",
            "message": "urgent",
            "priority": 2,
            "title": "Alert",
            "sound": "siren",
            "retry": 60,
            "expire": 10800,
        },
        timeout=15,
    )


@patch("pushover.requests.post")
def test_send_pushover_raises_on_non_200(mock_post):
    mock_post.return_value = MagicMock(status_code=400, text="invalid token")

    with pytest.raises(PushoverError):
        send_pushover("user123", "token456", message="hello")


@pytest.mark.parametrize(
    "network_exc",
    [
        requests.ConnectionError("no route to host"),
        requests.Timeout("timed out"),
    ],
)
@patch("pushover.requests.post")
def test_send_pushover_wraps_network_errors_in_pushover_error(mock_post, network_exc):
    # Callers (watch.py) catch PushoverError to decide whether an alert got through;
    # a raw requests exception would sail straight past those handlers.
    mock_post.side_effect = network_exc

    with pytest.raises(PushoverError) as exc_info:
        send_pushover("user123", "token456", message="hello")

    assert exc_info.value.__cause__ is network_exc
