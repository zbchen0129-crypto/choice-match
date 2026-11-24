"""Responses API adapter. Settings loaded by entry points; no key logging."""
import json
import os
import urllib.error
import urllib.request


class ModelError(RuntimeError):
    pass


class OpenAIModel:
    def __init__(self):
        self.key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL")
        if not self.key or not self.model:
            raise ModelError("Set OPENAI_API_KEY and OPENAI_MODEL in the process environment.")

    def complete(self, name, schema, instructions, data):
        payload = {"model": self.model, "store": False, "max_output_tokens": 5000,
                   "input": [{"role": "developer", "content": instructions},
                             {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
                   "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}}}
        request = urllib.request.Request("https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise ModelError("Model response exceeds 4 MiB budget.")
                result = json.loads(body)
        except urllib.error.HTTPError as exc:
            raise ModelError(f"Model request failed (HTTP {exc.code}); response body withheld.") from None
        except (urllib.error.URLError, TimeoutError):
            raise ModelError("Model request timed out or could not connect.") from None
        return decode_response(result)


def decode_response(result):
    if result.get("status") != "completed":
        raise ModelError("Model response is incomplete.")
    content = [part for item in result.get("output", []) for part in item.get("content", [])]
    if any(part.get("type") == "refusal" for part in content):
        raise ModelError("Model declined this request.")
    try:
        return json.loads("".join(part["text"] for part in content if part.get("type") == "output_text"))
    except (ValueError, KeyError):
        raise ModelError("Model response contains no valid JSON.") from None
