
from flask import Flask, render_template, request, jsonify
from pathlib import Path
from web_evaluator import process_uploaded_zip

import zipfile
import uuid
import json
import shutil
import stat

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"

UPLOAD_DIR.mkdir(exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

ALLOWED_FILES = {".txt"}
MAX_FILES = 500
MAX_EXTRACTED_SIZE = 100 * 1024 * 1024


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload_zip():

    if "file" not in request.files:
        return jsonify({"error": "No file selected"}), 400

    file = request.files["file"]

    if not file.filename.lower().endswith(".zip"):
        return jsonify({"error": "Only ZIP files allowed"}), 400

    job_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir()

    zip_path = job_dir / "upload.zip"
    file.save(zip_path)

    transcripts = []

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:

            members = archive.infolist()

            if len(members) > MAX_FILES:
                raise ValueError("Too many files in ZIP")

            total_size = 0

            for member in members:

                if member.is_dir():
                    continue

                original_name = member.filename
                normalized = original_name.replace("\\", "/")
                parts = Path(normalized).parts

                if (
                    normalized.startswith("/")
                    or ".." in parts
                    or ":" in normalized
                ):
                    raise ValueError("Unsafe ZIP path")

                # Reject symbolic links in the ZIP.
                mode = member.external_attr >> 16
                if stat.S_IFMT(mode) == stat.S_IFLNK:
                    raise ValueError("Symbolic links are not allowed")

                if Path(normalized).suffix.lower() not in ALLOWED_FILES:
                    continue

                total_size += member.file_size

                if total_size > MAX_EXTRACTED_SIZE:
                    raise ValueError("ZIP contents are too large")

                saved_name = (
                    f"episode_file_{len(transcripts) + 1}.txt"
                )

                output_path = job_dir / saved_name

                with archive.open(member) as source:
                    with output_path.open("wb") as target:

                        remaining = member.file_size

                        while remaining > 0:
                            chunk = source.read(
                                min(1024 * 1024, remaining)
                            )

                            if not chunk:
                                raise ValueError(
                                    "Incomplete ZIP entry"
                                )

                            target.write(chunk)
                            remaining -= len(chunk)

                transcripts.append({
                    "original_name": original_name,
                    "saved_name": saved_name
                })

        zip_path.unlink(missing_ok=True)

        if not transcripts:
            raise ValueError(
                "No TXT transcripts found in ZIP"
            )

        # Run the existing evaluation pipeline.
        evaluation = process_uploaded_zip(job_dir)

        return jsonify({
            "message": "Evaluation completed successfully",
            "job_id": job_id,
            "total_transcripts": len(transcripts),
            "transcripts": transcripts,
            "episodes_processed":
                evaluation["episodes_processed"],
            "candidates_evaluated":
                evaluation["candidates_evaluated"],
            "top20": evaluation["top20"],
            "status": "completed"
        })

    except (
        zipfile.BadZipFile,
        ValueError,
        UnicodeError,
        OSError
    ) as e:

        shutil.rmtree(job_dir, ignore_errors=True)

        return jsonify({
            "error": str(e)
        }), 400

    except Exception:
        app.logger.exception("Evaluation failed")

        shutil.rmtree(job_dir, ignore_errors=True)

        return jsonify({
            "error": "Evaluation failed. Check server logs."
        }), 500

    finally:
        zip_path.unlink(missing_ok=True)


@app.route("/api/results")
def get_results():

    path = RESULTS_DIR / "final_top20.json"

    if not path.exists():
        return jsonify({
            "error": "Previous results not found"
        }), 404

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return jsonify(data)


@app.route("/api/results/<job_id>")
def get_job_results(job_id):

    if (
        len(job_id) != 32
        or any(c not in "0123456789abcdef" for c in job_id)
    ):
        return jsonify({"error": "Invalid job ID"}), 400

    path = (
        UPLOAD_DIR
        / job_id
        / "evaluation_results"
        / "final_top20.json"
    )

    if not path.exists():
        return jsonify({"error": "Results not found"}), 404

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)
