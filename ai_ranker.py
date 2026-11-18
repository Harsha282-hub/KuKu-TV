
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=api_key)


def evaluate_clip(candidate):

    screenplay = "\n".join(
        f"[{e['start']:.2f}-{e['end']:.2f}] "
        f"{e['speaker'] or e['type']}: {e['text']}"
        for e in candidate["events"]
        if e["start"] >= candidate["start"]
        and e["end"] <= candidate["end"]
    )

    prompt = f"""
You are an expert short-form drama promo editor.

Evaluate this candidate promotional clip.

Episode: {candidate['episode']}
Start: {candidate['start']} seconds
End: {candidate['end']} seconds
Duration: {candidate['duration']} seconds

SCREENPLAY:
{screenplay}

Score these criteria from 0 to 10:

1. hook_score:
Does the first 3 seconds grab attention?

2. cliffhanger_score:
Does the clip end with unresolved tension?

3. clarity_score:
Can someone unfamiliar with the story understand it?

4. emotion_score:
Is the clip emotionally engaging?

Be strict and evidence-based.
Do not invent events or dialogue.
Penalize weak hooks, weak cliffhangers, and cut-off dialogue.

Return JSON containing exactly:
hook_score, cliffhanger_score, clarity_score,
emotion_score, hook, cliffhanger, rationale.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert drama promo evaluator."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )

    result = json.loads(
        response.choices[0].message.content
    )

    result["episode"] = candidate["episode"]
    result["start"] = candidate["start"]
    result["end"] = candidate["end"]
    result["duration"] = candidate["duration"]

    result["overall_score"] = round(
        result["hook_score"] * 0.35 +
        result["cliffhanger_score"] * 0.30 +
        result["clarity_score"] * 0.25 +
        result["emotion_score"] * 0.10,
        2
    )

    return result
