"""A pretend web client for tests: returns canned API responses, never uses the internet."""


class FakeClient:
    def __init__(self, routes: dict):
        # routes: {url_substring: response}. A response that is an Exception is raised.
        self.routes = routes
        self.calls: list[tuple[str, str, object]] = []

    def _answer(self, method, url, body):
        self.calls.append((method, url, body))
        # Longest matching key wins, so ".../postings/123" beats ".../postings".
        for key in sorted(self.routes, key=len, reverse=True):
            if key in url:
                value = self.routes[key]
                if isinstance(value, Exception):
                    raise value
                return value(body) if callable(value) else value
        raise AssertionError(f"FakeClient has no route for {url}")

    def get_json(self, url, params=None):
        return self._answer("GET", url, params)

    def post_json(self, url, payload):
        return self._answer("POST", url, payload)


SETTINGS = {
    "title_include": ["fp&a", "cost", "costing", "financial analyst", "finance analyst",
                      "management account", "budget", "mis"],
    "ats_keywords": ["finance"],
    "search_terms": ["FP&A analyst"],
    "locations": ["Chennai", "Remote"],
    "max_job_age_days": 30,
}
