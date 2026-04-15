import logging
import os
import random
import secrets
import time

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-419,es;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
    },
]


class MagneticProxy:
    HOST = "rs.magneticproxy.net"
    PORT = 1080

    def __init__(self, username=None, password=None):
        self.username = username or os.getenv("MAGNETIC_USERNAME")
        self.password = password or os.getenv("MAGNETIC_PASSWORD")
        if not self.username or not self.password:
            raise ValueError(
                "MagneticProxy credentials not found. "
                "Set MAGNETIC_USERNAME and MAGNETIC_PASSWORD in .env"
            )
        self._current_headers = random.choice(HEADERS_POOL)
        self._consecutive_failures = 0
        self._last_success_time = time.time()

    @property
    def consecutive_failures(self):
        return self._consecutive_failures

    def _build_username(self, country=None, city=None, session_id=None):
        parts = [f"customer-{self.username}"]
        if country:
            parts.append(f"cc-{country}")
        if city:
            parts.append(f"city-{city}")
        if session_id:
            parts.append(f"sessid-{session_id}")
        return "-".join(parts)

    def get_proxies(self, country=None, city=None, session_id=None):
        user = self._build_username(country, city, session_id)
        proxy_url = f"http://{user}:{self.password}@{self.HOST}:{self.PORT}"
        return {"http": proxy_url, "https": proxy_url}

    def new_session(self):
        return secrets.token_hex(4)

    def rotate_headers(self):
        self._current_headers = random.choice(HEADERS_POOL)
        return self._current_headers

    def health_check(self, country=None, city=None, max_attempts=5):
        base_wait = 10
        for attempt in range(max_attempts):
            session_id = self.new_session()
            proxies = self.get_proxies(country, city, session_id)
            try:
                resp = requests.get(
                    "https://www.google.com/generate_204",
                    proxies=proxies,
                    timeout=15,
                )
                if resp.status_code in (200, 204):
                    logger.info("Proxy health check passed (attempt %d/%d)",
                                attempt + 1, max_attempts)
                    self._consecutive_failures = 0
                    return True
            except (requests.exceptions.ProxyError,
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                pass

            wait = base_wait * (2 ** attempt)
            logger.warning(
                "Proxy health check failed (attempt %d/%d), waiting %ds...",
                attempt + 1, max_attempts, wait,
            )
            time.sleep(wait)

        logger.error("Proxy health check FAILED after %d attempts", max_attempts)
        return False

    def warmup(self, country=None, city=None):
        logger.info("Running proxy warmup check...")
        if not self.health_check(country=country, city=city):
            raise ConnectionError("Proxy not reachable during warmup. Aborting.")
        logger.info("Proxy warmup successful.")

    def make_request(
        self,
        url,
        country=None,
        city=None,
        session_id=None,
        max_retries=7,
        timeout=(15, 45),
    ):
        base_delay = 5

        # Circuit breaker: if proxy has been consistently failing, verify it first
        if self._consecutive_failures >= 3:
            logger.warning(
                "Circuit breaker: %d consecutive request failures, running health check...",
                self._consecutive_failures,
            )
            if not self.health_check(country=country, city=city):
                logger.error("Proxy appears down. Waiting 120s before continuing...")
                time.sleep(120)

        for attempt in range(max_retries):
            proxies = self.get_proxies(country, city, session_id)
            try:
                response = requests.get(
                    url,
                    headers=self._current_headers,
                    proxies=proxies,
                    timeout=timeout,
                )

                if response.status_code == 200:
                    body = response.text
                    if "<title>Sorry</title>" in body or "recaptcha" in body.lower():
                        logger.warning(
                            "CAPTCHA detected (attempt %d/%d)",
                            attempt + 1,
                            max_retries,
                        )
                        wait = random.uniform(30, 60)
                        time.sleep(wait)
                        session_id = self.new_session()
                        self.rotate_headers()
                        continue
                    self._consecutive_failures = 0
                    self._last_success_time = time.time()
                    return response

                if response.status_code in (429, 403, 503):
                    logger.warning(
                        "HTTP %d (attempt %d/%d)",
                        response.status_code,
                        attempt + 1,
                        max_retries,
                    )
                    wait = base_delay * (2 ** attempt) + random.uniform(2, 8)
                    time.sleep(wait)
                    session_id = self.new_session()
                    self.rotate_headers()
                    continue

                logger.warning(
                    "HTTP %d (attempt %d/%d)",
                    response.status_code,
                    attempt + 1,
                    max_retries,
                )
                wait = base_delay * (2 ** attempt) + random.uniform(1, 3)
                time.sleep(wait)
                session_id = self.new_session()
                self.rotate_headers()

            except requests.exceptions.ProxyError:
                logger.warning(
                    "Proxy error (attempt %d/%d)", attempt + 1, max_retries
                )
                wait = base_delay * (2 ** attempt) + random.uniform(2, 5)
                time.sleep(wait)
                session_id = self.new_session()
                self.rotate_headers()

            except requests.exceptions.Timeout:
                logger.warning("Timeout (attempt %d/%d)", attempt + 1, max_retries)
                wait = base_delay * (2 ** attempt) + random.uniform(2, 5)
                time.sleep(wait)
                session_id = self.new_session()
                self.rotate_headers()

            except requests.exceptions.ConnectionError:
                logger.warning(
                    "Connection error (attempt %d/%d)", attempt + 1, max_retries
                )
                wait = base_delay * (2 ** attempt) + random.uniform(2, 5)
                time.sleep(wait)
                session_id = self.new_session()
                self.rotate_headers()

        self._consecutive_failures += 1
        logger.error(
            "All %d retries exhausted for %s (consecutive failures: %d)",
            max_retries, url, self._consecutive_failures,
        )
        return None
