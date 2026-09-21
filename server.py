import json
import os
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from tts_engine import TTSEngine

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR = BASE_DIR / "static"
HISTORY_PATH = OUTPUT_DIR / "history.json"
HISTORY_LIMIT = 50

MAX_CHARS = 5000

app = Flask(__name__, static_folder=None)
engine = TTSEngine()

jobs = {}
jobs_lock = threading.Lock()
history_lock = threading.Lock()


def load_history():
	if not HISTORY_PATH.exists():
		return []
	try:
		return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
	except (json.JSONDecodeError, OSError):
		return []


def append_history(record):
	with history_lock:
		history = load_history()
		history.append(record)
		history = history[-HISTORY_LIMIT:]
		HISTORY_PATH.write_text(json.dumps(history), encoding="utf-8")


def run_job(job_id, text, output_path):
	def on_progress(done, total):
		with jobs_lock:
			jobs[job_id]["completed"] = done
			jobs[job_id]["total"] = total

	try:
		engine.generate_to_file(text, str(output_path), on_progress=on_progress)
		url = f"/outputs/{output_path.name}"
		with jobs_lock:
			jobs[job_id]["status"] = "done"
			jobs[job_id]["url"] = url
		append_history({
			"id": job_id,
			"text": text,
			"url": url,
			"created_at": jobs[job_id]["created_at"],
		})
	except Exception as exc:
		with jobs_lock:
			jobs[job_id]["status"] = "error"
			jobs[job_id]["error"] = str(exc)


@app.get("/")
def index():
	return send_from_directory(STATIC_DIR, "index.html")


@app.get("/static/<path:filename>")
def static_files(filename):
	return send_from_directory(STATIC_DIR, filename)


@app.get("/outputs/<path:filename>")
def output_files(filename):
	return send_from_directory(OUTPUT_DIR, filename)


@app.get("/api/status")
def status():
	return jsonify({"ready": engine._model is not None})


@app.post("/api/generate")
def generate():
	data = request.get_json(silent=True) or {}
	text = (data.get("text") or "").strip()

	if not text:
		return jsonify({"error": "Enter some text first."}), 400
	if len(text) > MAX_CHARS:
		return jsonify({"error": f"Text is too long (max {MAX_CHARS} characters)."}), 400

	job_id = uuid.uuid4().hex
	output_path = OUTPUT_DIR / f"{job_id}.mp3"

	with jobs_lock:
		jobs[job_id] = {
			"status": "running",
			"completed": 0,
			"total": None,
			"text": text,
			"url": None,
			"error": None,
			"created_at": time.time(),
		}

	threading.Thread(target=run_job, args=(job_id, text, output_path), daemon=True).start()
	return jsonify({"job_id": job_id})


@app.get("/api/generate/<job_id>")
def job_status(job_id):
	with jobs_lock:
		job = jobs.get(job_id)
		if job is None:
			return jsonify({"error": "Unknown job."}), 404
		return jsonify(job)


@app.get("/api/history")
def history():
	return jsonify(load_history())


@app.delete("/api/history")
def clear_history():
	with history_lock:
		for record in load_history():
			file_path = OUTPUT_DIR / Path(record["url"]).name
			file_path.unlink(missing_ok=True)
		HISTORY_PATH.unlink(missing_ok=True)
	return jsonify({"ok": True})


if __name__ == "__main__":
	# Warm the model up in the background so the first click from the UI
	# doesn't have to eat the (slow) model + reference-conditioning load.
	threading.Thread(target=engine.ensure_loaded, daemon=True).start()
	# HOST=0.0.0.0 is required in a container (Render/HF Spaces) so the
	# platform's proxy can reach the process; local dev keeps 127.0.0.1.
	host = os.environ.get("HOST", "127.0.0.1")
	port = int(os.environ.get("PORT", 7860))
	app.run(host=host, port=port, threaded=True)
