import base64
import json
import re


_PROMPT = (
    "You are analyzing a treadmill run-summary display. "
    "Extract the run stats and return ONLY valid JSON with these keys "
    "(use null for any value not visible): "
    '{"distance": <float km or miles>, "duration": <float minutes>, '
    '"pace": <float min/km or min/mile>, "calories": <int or null>, "incline": <float or null>}. '
    "Do not include any explanation."
)


def _call_claude_vision(image_bytes: bytes, media_type: str, model: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    b64 = base64.standard_b64encode(image_bytes).decode()
    message = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    )
    text = message.content[0].text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def extract_run_stats(path: str, model: str) -> dict:
    import mimetypes

    media_type, _ = mimetypes.guess_type(path)
    if not media_type:
        media_type = "image/jpeg"

    with open(path, "rb") as f:
        image_bytes = f.read()

    stats = _call_claude_vision(image_bytes, media_type, model)

    # Derive pace from distance + duration when pace is absent
    if not stats.get("pace") and stats.get("distance") and stats.get("duration"):
        try:
            stats["pace"] = stats["duration"] / stats["distance"]
        except ZeroDivisionError:
            stats["pace"] = None

    return stats
