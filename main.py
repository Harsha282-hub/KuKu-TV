import json
from ai_ranker import evaluate_clip
from pathlib import Path
import re

def read_episodes(folder):
    episodes = []

    for file in Path(folder).iterdir():

        if not file.is_file() or file.suffix.lower() != ".txt":
            continue

        text = file.read_text(encoding="utf-8-sig")

        match = re.search(
            r"EPISODE NUMBER:\s*Episode\s*(\d+)",
            text,
            re.IGNORECASE
        )

        if not match:
            print("Episode number not found:", file.name)
            continue

        episode_number = int(match.group(1))

        episodes.append({
            "episode": episode_number,
            "filename": file.name,
            "text": text
        })

    episodes.sort(key=lambda x: x["episode"])

    return episodes


def to_seconds(timestamp):
    minutes, seconds = timestamp.split(":")
    return int(minutes) * 60 + float(seconds)


def extract_events(text):
    events = []

    pattern = re.compile(
        r"^\*\*(.+?):\*\*\s*\n"
        r"Start:\s*\((\d{2}:\d{2}\.\d+)\)\s*\|\s*"
        r"End:\s*\((\d{2}:\d{2}\.\d+)\)\s*\n"
        r"([\s\S]*?)(?=\n\s*\n|\Z)",
        re.MULTILINE
    )

    for match in pattern.finditer(text):
        heading = match.group(1).strip()
        start = to_seconds(match.group(2))
        end = to_seconds(match.group(3))
        content = match.group(4).strip()

        if heading in ["CAMERA", "ACTION", "SOUND FX"]:
            event_type = heading.lower()
            speaker = None
        else:
            event_type = "dialogue"
            speaker = heading.split("(")[0].strip()

        events.append({
            "type": event_type,
            "speaker": speaker,
            "start": start,
            "end": end,
            "text": content
        })

    events.sort(key=lambda x: x["start"])

    return events
##3rd code

def generate_candidates(episode, min_duration=20, max_duration=60):
    events = episode["events"]
    candidates = []

    if not events:
        return candidates

    # Use event boundaries instead of arbitrary timestamps
    boundaries = sorted(set(
        [event["start"] for event in events] +
        [event["end"] for event in events]
    ))

    for i in range(len(boundaries)):
        start = boundaries[i]

        for j in range(i + 1, len(boundaries)):
            end = boundaries[j]
            duration = end - start

            if duration < min_duration:
                continue

            if duration > max_duration:
                break

            selected_events = [
                event for event in events
                if event["start"] < end and event["end"] > start
            ]

            if not selected_events:
                continue

            candidates.append({
                "episode": episode["episode"],
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(duration, 2),
                "events": selected_events
            })

    return candidates

##4th input

def shortlist_candidates(candidates, limit=10):
    if not candidates:
        return []

    scored = []

    for candidate in candidates:
        events = candidate["events"]
        start = candidate["start"]
        end = candidate["end"]

        # Prefer dialogue and action over camera descriptions
        important = [
            e for e in events
            if e["type"] in ("dialogue", "action")
        ]

        if not important:
            continue

        # Reward dialogue/action near the beginning
        opening = sum(
            1 for e in important
            if e["start"] < start + 3
            and e["end"] > start
        )

        # Reward dialogue/action near the ending
        ending = sum(
            1 for e in important
            if e["start"] < end
            and e["end"] > end - 5
        )

        # Prefer duration near 40 seconds
        duration_score = 1 - abs(candidate["duration"] - 40) / 40

        score = (
            opening * 3 +
            ending * 2 +
            duration_score
        )

        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected = []

    for score, candidate in scored:
        if len(selected) >= limit:
            break

        # Avoid candidates that are nearly identical
        duplicate = False

        for existing in selected:
            overlap = max(
                0,
                min(candidate["end"], existing["end"])
                - max(candidate["start"], existing["start"])
            )

            shorter_duration = min(
                candidate["duration"],
                existing["duration"]
            )

            if overlap / shorter_duration > 0.5:
                duplicate = True
                break

        if not duplicate:
            candidate["pre_score"] = round(score, 2)
            selected.append(candidate)

    return selected
def get_shortlisted_clips():
    episodes = read_episodes("input")
    all_shortlisted = []

    for ep in episodes:
        ep["events"] = extract_events(ep["text"])
        candidates = generate_candidates(ep)
        shortlisted = shortlist_candidates(candidates, limit=10)
        all_shortlisted.extend(shortlisted)

    return all_shortlisted


if __name__ == "__main__":
    all_shortlisted = get_shortlisted_clips()

    print("Total shortlisted clips:", len(all_shortlisted))
