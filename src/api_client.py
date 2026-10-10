"""HTTP helpers for the BarentsWatch API: token handling and a robust GET."""
import os
import sys
import time
from collections import Counter

import requests

TOKEN_URL = "https://id.barentswatch.no/connect/token"
REFRESH_MARGIN_S = 300
DEFAULT_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT", 20))

# Filled by make_request and printed in the run summary.
STATUS_COUNTS = Counter()


class TokenManager:
    """Fetches an OAuth2 token and renews it shortly before it expires."""

    def __init__(self):
        self.client_id = os.environ.get("BW_CLIENT_ID")
        self.client_secret = os.environ.get("BW_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            print("ERROR: BW_CLIENT_ID or BW_CLIENT_SECRET is not set (see .env.example).")
            sys.exit(1)
        self._token = None
        self._expires_at = 0.0

    def _fetch(self, max_attempts=3):
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "api",
        }
        for attempt in range(max_attempts):
            try:
                response = requests.post(TOKEN_URL, data=data, timeout=15)
            except requests.exceptions.RequestException as exc:
                print(f"WARNING: token request failed ({type(exc).__name__}), "
                      f"attempt {attempt + 1}/{max_attempts}.")
            else:
                if response.status_code == 200:
                    try:
                        body = response.json()
                        self._token = body["access_token"]
                        self._expires_at = time.time() + int(body.get("expires_in", 3600))
                    except (ValueError, KeyError):
                        print("ERROR: unexpected token response format.")
                        sys.exit(1)
                    return
                if response.status_code != 429 and response.status_code < 500:
                    print(f"ERROR: authentication failed (HTTP {response.status_code}). "
                          "Check BW_CLIENT_ID / BW_CLIENT_SECRET. Not retrying.")
                    sys.exit(1)
                print(f"WARNING: token endpoint returned HTTP {response.status_code}, "
                      f"attempt {attempt + 1}/{max_attempts}.")
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
        print("ERROR: could not obtain a token after retries.")
        sys.exit(1)

    def get(self):
        if self._token is None or time.time() > self._expires_at - REFRESH_MARGIN_S:
            self._fetch()
        return self._token


def _retry_delay(response, attempt):
    base = min(2 ** attempt, 60)
    retry_after = response.headers.get("Retry-After", "")
    return max(base, int(retry_after)) if retry_after.isdigit() else base


def make_request(url, tokens, timeout=DEFAULT_TIMEOUT_S, max_retries=5):
    """GET with timeout, bounded backoff on 429/5xx/network errors, hard stop on 401/403.

    Returns the response (any status < 500 except 429) or None if all attempts failed.
    """
    for attempt in range(max_retries):
        headers = {"Authorization": f"Bearer {tokens.get()}"}
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            STATUS_COUNTS[type(exc).__name__] += 1
            delay = min(2 ** attempt, 60)
            print(f"WARNING: {type(exc).__name__} on {url} "
                  f"(attempt {attempt + 1}/{max_retries}).")
        else:
            STATUS_COUNTS[str(response.status_code)] += 1
            if response.status_code in (401, 403):
                print(f"FATAL: authentication error HTTP {response.status_code} on {url}. "
                      "Stopping, no retry.")
                sys.exit(1)
            if response.status_code != 429 and response.status_code < 500:
                return response
            delay = _retry_delay(response, attempt)
            print(f"WARNING: HTTP {response.status_code} on {url} "
                  f"(attempt {attempt + 1}/{max_retries}).")
        if attempt < max_retries - 1:
            time.sleep(delay)
    print(f"ERROR: giving up after {max_retries} attempts: {url}")
    return None