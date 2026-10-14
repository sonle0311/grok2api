"""Call grok2api instead of the KTV provider router."""

import json
import urllib.request


class GrokClient:
    def __init__(self, base_url: str, api_key: str, chat_model: str = "grok-4.5"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.chat_model = chat_model

    def chat_json(self, system: str, user: str) -> dict:
        from story_studio.jsonutil import extract_json

        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        body = self._post("/v1/chat/completions", payload)
        content = body["choices"][0]["message"]["content"]
        return extract_json(content)

    def _post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
