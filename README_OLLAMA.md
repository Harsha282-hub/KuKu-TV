# Kuku TV: local Ollama LLM evaluation (16 GB RAM)

This is an **add-on**, not a replacement for `main.py` or `run_pipeline.py`.

## Installation (Windows)

1. Install Ollama from https://ollama.com/download/windows and open Ollama.
2. In PowerShell run `ollama pull qwen2.5:7b` (model download requires internet **once**). This is a reasonable first attempt for 16 GB RAM; CPU-only inference may be slow. If it cannot run comfortably, try `ollama pull qwen2.5:3b` and pass `--model qwen2.5:3b` to the script.
3. Check `ollama list` to confirm the model is installed.
4. Put `ollama_evaluate.py` beside your existing `run_pipeline.py`. Ensure `data/shortlisted_clips.json` is present.

## Commands

```powershell
cd 'D:\KK TV'
python ollama_evaluate.py --limit 3
python ollama_evaluate.py
```

The first command tests 3 candidates; the second processes the entire set, reusing those 3 cached responses. If interrupted, rerun the same command to resume. Use `--export-only` to rebuild output CSV/JSON from existing cache without contacting Ollama. If Ollama isn't running, launch the desktop app or run `ollama serve` in a separate terminal.

## Outputs

- `cache/ollama/clip_XXX_HASH.json`: one validated, atomic cache file per clip. Cache key includes clip content, model, temperature, prompt version; changes automatically trigger reevaluation.
- `results/ollama_evaluations.json`: all successfully evaluated clips, including evidence and rationale.
- `results/ollama_ranked_promos.csv`: LLM-scored clips ranked by 0.35 hook + 0.30 cliffhanger + 0.25 clarity + 0.10 emotion.
- `results/ollama_failures.json`: failed clip IDs if any; rerunning retries these.

**Do not report full coverage until the terminal prints `Complete: 215/215 evaluated`.** This script does not replace the editorial Top 20 automatically. Review top-ranked results and verify timestamps, standalone clarity, overlap, and scene diversity first. Local model outputs are still fallible, especially for precise 3-second hook timing. Human/video verification is required before final submission.

## Privacy and reproducibility

The Ollama HTTP request goes to `127.0.0.1:11434` by default; do not change `--url` to a remote endpoint for confidential screenplays. The model must be downloaded beforehand. Temperature is zero, seed is fixed, and output is validated against numeric score bounds and required evidence fields. Model implementations/hardware can still vary. To reproduce results exactly, retain the cached outputs, model version and the input JSON. Avoid publicly publishing screenplay text or cached excerpts.

## Troubleshooting

- `Connection refused`: launch Ollama or `ollama serve`.
- `model not found`: run `ollama pull qwen2.5:7b` or specify a model already shown by `ollama list`.
- `out of memory` or excessive slowness: try `qwen2.5:3b`; different model uses separate cache keys and cannot be mixed into one ranking.
- `timeout`: try `python ollama_evaluate.py --timeout 600`.
- Missing or invalid JSON: the script retries; failed clips are logged and can be retried in a subsequent run.

Python 3.9+; no pip packages, paid API key, or cloud inference needed.
