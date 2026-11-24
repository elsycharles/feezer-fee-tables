"""Polite HTTP access: honest user agent, robots.txt, timeouts."""

from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = (
    "FeezerFeeTablesBot/1.0 "
    "(+https://github.com/elsycharles/feezer-fee-tables)"
)
TIMEOUT = 30


class Fetcher:
    """Downloads pages once per run, refusing URLs disallowed by robots.txt."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": USER_AGENT, "Accept-Language": "fr,en;q=0.8"}
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _allowed(self, url: str) -> bool:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                response = self.session.get(f"{origin}/robots.txt", timeout=TIMEOUT)
            except requests.RequestException:
                response = None
            if response is not None and response.status_code == 200:
                parser.parse(response.text.splitlines())
                self._robots[origin] = parser
            else:
                self._robots[origin] = None  # no robots.txt: nothing disallowed
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> requests.Response:
        if not self._allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        response = self.session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        return response
