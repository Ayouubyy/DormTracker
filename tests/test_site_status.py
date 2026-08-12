from unittest.mock import MagicMock, patch

import requests

from site_status import is_site_up


@patch("site_status.requests.get")
def test_up_for_200(mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    assert is_site_up("https://example.com") is True


@patch("site_status.requests.get")
def test_down_for_500(mock_get):
    # Real observed behavior from supcom.tn during its outage.
    mock_get.return_value = MagicMock(status_code=500)
    assert is_site_up("https://www.supcom.tn/") is False


@patch("site_status.requests.get")
def test_down_for_401_basic_auth_maintenance_gate(mock_get):
    # Real observed behavior from inscription.tn's maintenance gate (a native browser
    # Basic Auth prompt, not their real login page).
    mock_get.return_value = MagicMock(status_code=401)
    assert is_site_up("https://www.inscription.tn/") is False


@patch("site_status.requests.get")
def test_down_on_network_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("no route to host")
    assert is_site_up("https://example.com") is False
