
import json
import csv
import time
from pathlib import Path

from main import get_shortlisted_clips
from ai_ranker import evaluate_clip

OUTPUT = Path("results")
OUTPUT.mkdir(exist_ok=True)

JSON_FILE = OUTPUT / "openai_evaluations.json"
CSV_FILE = OUTPUT / "openai_ranked_promos.csv"


def clip_id(clip):
    return (
        f"{clip['episode']}_"
        f"{clip['start']:.2f}_"
        f"{clip['end']:.2f}"
    )


def save_results(results):
    # Save JSON first
    JSON_FILE.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8"
    )

    ranked = sorted(
        results,
        key=lambda x: x["overall_score"],
        reverse=True
    )

    fields = [
        "rank", "episode", "start", "end",
        "duration", "overall_score",
        "hook_score", "cliffhanger_score",
        "clarity_score", "emotion_score",
        "hook", "cliffhanger", "rationale"
    ]

    try:
        with CSV_FILE.open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fields,
                extrasaction="ignore"
            )

            writer.writeheader()

            for rank, result in enumerate(ranked, start=1):
                writer.writerow({
                    **result,
                    "rank": rank
                })

    except PermissionError:
        print(
            "Warning: CSV file is locked. "
            "JSON results are saved."
        )


def main():
    # Test only one clip for now
    clips = get_shortlisted_clips()[:1]

    if JSON_FILE.exists():
        results = json.loads(
            JSON_FILE.read_text(encoding="utf-8")
        )
    else:
        results = []

    completed = {
        clip_id(result) for result in results
    }

    print("Total clips:", len(clips))
    print("Already evaluated:", len(completed))

    for index, clip in enumerate(clips, start=1):
        key = clip_id(clip)

        if key in completed:
            continue

        print(
            f"Evaluating {index}/{len(clips)}: "
            f"Episode {clip['episode']}"
        )

        result = None

        # Only one attempt while diagnosing API errors
        try:
            result = evaluate_clip(clip)

        except Exception as error:
            print("\nActual OpenAI API error:")
            print(str(error))

        if result is None:
            print("\nEvaluation failed. Check the API error above.")
            break

        results.append(result)
        completed.add(key)

        save_results(results)

        print("Score:", result["overall_score"])

        time.sleep(5)

    print("\nEvaluations saved:", len(results))
    print("JSON:", JSON_FILE)
    print("CSV:", CSV_FILE)


if __name__ == "__main__":
    main()
 