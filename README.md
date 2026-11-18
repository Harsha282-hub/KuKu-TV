# Kuku TV — Offline Promo Selection Prototype

## Run on Windows (PowerShell)

```powershell
cd 'D:\KK TV'
python run_pipeline.py
```

Copy `run_pipeline.py`, `data/`, and `results/` from this package into `D:\KK TV` first. Python 3.9+ is required; no `pip install`, API key, internet connection, or paid credits are needed.

**Outputs:**
- `results/all_evaluations.json` — 215 candidates with scores and assessment type
- `results/ranked_promos.csv` — all candidates ordered by weighted score
- `results/final_top20.csv` — editorially curated selection, in priority order
- `results/final_top20.json` — same curated selection in JSON

## Keep the existing `main.py`

Your original `main.py` can remain unchanged. The default run uses the bundled exported `data/shortlisted_clips.json` snapshot so the demo works even when the 50 episode text files are not present.

If you want to re-extract candidates from your original `main.py`, place this script beside it and run:

```powershell
python run_pipeline.py --from-main
```

`main.py` must expose `get_shortlisted_clips()` and your original `inputs/` directory must be available. Clip IDs are assigned in extractor output order. **If the extractor's ordering changes, the saved 1–25 editorial scores and curated top-20 IDs may no longer match.** Revalidate them before using `--from-main` results.

## How it works

1. Load shortlisted candidates, each with episode, timestamps and screenplay events.
2. Score opening 3 seconds (hook), last 7 seconds (cliffhanger), dialogue/context (clarity), and dramatic language (emotion).
3. For clips 1–25, preserve earlier human/editorial screenplay ratings. For clips 26–215, use transparent deterministic **heuristic estimates**, not an LLM or manually validated ratings.
4. Weighted score = `0.35*hook + 0.30*cliffhanger + 0.25*clarity + 0.10*emotion`.
5. Sort all candidates and export ranked results. Export a separate editorially curated top-20 list that prioritizes variety and non-overlap, not just the numeric score.

## Limitations / quality assurance

- This prototype analyzes screenplay text, not video or sound. Hook quality, pacing, performance, and actual end cuts require footage review.
- The curated top-20 list is a **provisional recommendation**, not a verified video-ready deliverable.
- The top-20 editorial order is not the same as numeric rank; `previous_score` and `score_type` in the curated data indicate provenance.
- Keyword-based scoring can overrate intense words and miss subtle storytelling. Scores are screening aids, not audience-retention predictions.
- Treat episode screenplays and exported snippets as confidential; do not publish this folder publicly.
