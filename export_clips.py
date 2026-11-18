
import json
from pathlib import Path
from main import get_shortlisted_clips

clips = get_shortlisted_clips()

output = []

for i, clip in enumerate(clips, start=1):
    events = []

    for event in clip["events"]:
        if (
            event["start"] >= clip["start"]
            and event["end"] <= clip["end"]
        ):
            events.append({
                "speaker": event["speaker"],
                "type": event["type"],
                "start": event["start"],
                "end": event["end"],
                "text": event["text"]
            })

    output.append({
        "clip_id": i,
        "episode": clip["episode"],
        "start": clip["start"],
        "end": clip["end"],
        "duration": clip["duration"],
        "events": events
    })

Path("results").mkdir(exist_ok=True)

Path("results/shortlisted_clips.json").write_text(
    json.dumps(output, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Exported clips:", len(output))
print("Saved to results/shortlisted_clips.json")
