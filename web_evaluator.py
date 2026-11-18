
import json
import csv
from pathlib import Path

from main import (
    read_episodes,
    extract_events,
    generate_candidates,
    shortlist_candidates
)

from run_pipeline import evaluate


def process_uploaded_zip(job_folder):
    job_folder = Path(job_folder)

    episodes = read_episodes(job_folder)

    if not episodes:
        raise ValueError("No valid episodes found in uploaded ZIP")

    all_shortlisted = []

    for episode in episodes:
        episode["events"] = extract_events(episode["text"])

        candidates = generate_candidates(episode)

        shortlisted = shortlist_candidates(
            candidates,
            limit=10
        )

        all_shortlisted.extend(shortlisted)

    if not all_shortlisted:
        raise ValueError(
            "No valid 20-60 second clips found in transcripts"
        )

    results = []

    for index, clip in enumerate(all_shortlisted, start=1):
        clip["clip_id"] = index

        # New uploads must not inherit the old
        # editorial scores for clip IDs 1-25.
        import run_pipeline
        original_reviewed = run_pipeline.REVIEWED

        try:
            run_pipeline.REVIEWED = {}
            result = evaluate(clip)
        finally:
            run_pipeline.REVIEWED = original_reviewed

        results.append(result)

    ranked = sorted(
        results,
        key=lambda r: (
            -r["overall_score"],
            -r["cliffhanger_score"],
            -r["hook_score"],
            r["clip_id"]
        )
    )

    for rank, result in enumerate(ranked, start=1):
        result["rank"] = rank

    top20 = ranked[:20]

    output_dir = job_folder / "evaluation_results"
    output_dir.mkdir(exist_ok=True)

    with open(
        output_dir / "all_evaluations.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(ranked, f, indent=2, ensure_ascii=False)

    with open(
        output_dir / "final_top20.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(top20, f, indent=2, ensure_ascii=False)

    if top20:
        with open(
            output_dir / "final_top20.csv",
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(top20[0].keys())
            )
            writer.writeheader()
            writer.writerows(top20)

    return {
        "episodes_processed": len(episodes),
        "candidates_evaluated": len(ranked),
        "top20": top20,
        "status": "completed"
    }
