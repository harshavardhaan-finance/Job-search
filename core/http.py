"""A polite web client that every collector shares (SPEC.md Section 1).

What "polite" means here:
- Read each site's robots.txt first and never fetch a page it disallows.
- Wait at least 2 seconds between requests to the same host.
- Say who we are with a clear User-Agent.
- If a host answers 429 (too many requests) or 403 (forbidden), stop using it
  for the rest of the day. The block is saved to a file so the next run that
  day also skips it.
"""
import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from core import config

log = logging.getLogger(__name__)

MIN_INTERVAL_SECONDS = 2.0
TIMEOUT_SECONDS = 30


class SourceBlocked(Exception):
    """The host refused us (429/403) or robots.txt disallows the page. Skip it."""


def default_user_agent() -> str:
    contact = os.getenv("CONTACT_EMAIL", "").strip()
    suffix = f"; contact: {contact}" if contact else ""
    return f"JobHuntCopilot/0.2 (personal job search, low volume{suffix})"


class PoliteClient:
    def __init__(
        self,
        min_interval: float = MIN_INTERVAL_SECONDS,
        block_file: Path | None = None,
        session: requests.Session | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        check_robots: bool = True,
    ):
        self.min_interval = min_interval
        self.block_file = Path(block_file) if block_file else config.ROOT / "data" / "blocked_hosts.json"
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = default_user_agent()
        self.session.headers["Accept"] = "application/json"
        self._sleep, self._clock = sleep, clock
        self.check_robots = check_robots
        self._last_request: dict[str, float] = {}   # host -> time of last request
        self._robots: dict[str, RobotFileParser | None] = {}
        self._unreachable: set[str] = set()          # hosts that failed to connect this run
        self.request_count = 0

    # ---- public API ---------------------------------------------------------

    def get_json(self, url: str, params: dict | None = None):
        return self._request("GET", url, params=params).json()

    def post_json(self, url: str, payload: dict):
        return self._request("POST", url, json=payload).json()

    # ---- the rules ----------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        host = urlparse(url).netloc
        if host in self._unreachable:
            raise SourceBlocked(f"{host} could not be reached earlier in this run; skipping")
        if self.is_blocked_today(host):
            raise SourceBlocked(f"{host} refused us earlier today; skipping until tomorrow")
        if self.check_robots and not self._robots_allows(url):
            raise SourceBlocked(f"robots.txt on {host} disallows {urlparse(url).path}")

        self._wait_turn(host)
        try:
            resp = self.session.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as e:
            # Site down, no internet, or a network filter: don't keep knocking this run.
            self._unreachable.add(host)
            raise SourceBlocked(f"{host} could not be reached ({type(e).__name__}); skipping for this run") from e
        self.request_count += 1
        if resp.status_code in (403, 429):
            self.block_host_today(host)
            raise SourceBlocked(f"{host} answered {resp.status_code}; skipping it for today")
        resp.raise_for_status()
        return resp

    def _wait_turn(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            gap = self._clock() - last
            if gap < self.min_interval:
                self._sleep(self.min_interval - gap)
        self._last_request[host] = self._clock()

    def _robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc
        if host not in self._robots:
            self._robots[host] = self._load_robots(f"{parsed.scheme}://{host}/robots.txt", host)
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(self.session.headers["User-Agent"], url)

    def _load_robots(self, robots_url: str, host: str) -> RobotFileParser | None:
        """Returns None when there is no usable robots.txt (that means: allowed)."""
        self._wait_turn(host)
        try:
            resp = self.session.get(robots_url, timeout=TIMEOUT_SECONDS, headers={"Accept": "text/plain"})
            self.request_count += 1
        except requests.RequestException as e:
            log.info("No robots.txt for %s (%s); treating as allowed", host, e)
            return None
        if resp.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser

    # ---- day-long blocks saved to disk --------------------------------------

    def _read_blocks(self) -> dict:
        try:
            return json.loads(self.block_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def is_blocked_today(self, host: str) -> bool:
        return self._read_blocks().get(host) == date.today().isoformat()

    def block_host_today(self, host: str) -> None:
        blocks = self._read_blocks()
        blocks[host] = date.today().isoformat()
        self.block_file.parent.mkdir(parents=True, exist_ok=True)
        self.block_file.write_text(json.dumps(blocks, indent=2), encoding="utf-8")
        log.warning("Blocking %s for today", host)
