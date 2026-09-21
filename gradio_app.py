# `spaces` must be imported before anything CUDA-related (torch, which
# tts_engine.py imports) - ZeroGPU patches CUDA init and errors out if
# that happens too late. Must stay the first import in this file.
try:
	import spaces
	HAS_ZEROGPU = True
except ImportError:
	HAS_ZEROGPU = False

import base64
import json
import os
import time
import uuid
from pathlib import Path

import gradio as gr

from tts_engine import TTSEngine

# This is the deployment entry point (Hugging Face Spaces, Gradio SDK -
# no card required, unlike the Docker SDK). Local development still uses
# server.py + static/ (the custom Flask UI) unchanged; this file adapts the
# same engine to Gradio's component model instead.
#
# On a ZeroGPU Space, generation needs to happen inside a function
# decorated with @spaces.GPU - that's the only window a GPU is actually
# attached. tts_engine.py auto-detects CUDA and uses it when present.
# Locally (no `spaces` package, or no GPU), this decorator is a no-op and
# generation runs on CPU exactly as before.
def gpu_decorator(duration=180):
	if HAS_ZEROGPU:
		return spaces.GPU(duration=duration)
	return lambda fn: fn

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
HISTORY_PATH = OUTPUT_DIR / "history.json"
HISTORY_LIMIT = 50
MAX_CHARS = 5000

engine = TTSEngine()


def load_history():
	if not HISTORY_PATH.exists():
		return []
	try:
		return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
	except (json.JSONDecodeError, OSError):
		return []


def append_history(record):
	history = load_history()
	history.append(record)
	history = history[-HISTORY_LIMIT:]
	HISTORY_PATH.write_text(json.dumps(history), encoding="utf-8")


def data_uri(path):
	data = Path(path).read_bytes()
	return f"data:image/png;base64,{base64.b64encode(data).decode()}"


@gpu_decorator(duration=180)
def generate(text, version, progress=gr.Progress()):
	text = (text or "").strip()
	if not text:
		raise gr.Error("Enter some text first.")
	if len(text) > MAX_CHARS:
		raise gr.Error(f"Text is too long (max {MAX_CHARS} characters).")

	progress(0, desc="Warming up the voice model (first generation only)..." if engine._model is None else "Starting...")

	job_id = uuid.uuid4().hex
	output_path = OUTPUT_DIR / f"{job_id}.mp3"

	def on_progress(done, total):
		progress(done / total, desc=f"Generating - part {done} of {total}")

	engine.generate_to_file(text, str(output_path), on_progress=on_progress)

	append_history({
		"text": text,
		"path": str(output_path),
		"created_at": time.time(),
	})

	return "", version + 1


def clear_history(version):
	for record in load_history():
		Path(record["path"]).unlink(missing_ok=True)
	HISTORY_PATH.unlink(missing_ok=True)
	return version + 1


LOGO_URI = data_uri(BASE_DIR / "static" / "assets" / "logo-wordmark.png")
STU_URI = data_uri(BASE_DIR / "static" / "assets" / "stu-avatar.png")

HEADER_HTML = f"""
<div class="studucate-brand">
	<img src="{LOGO_URI}" alt="Studucate" />
</div>
<h1 class="studucate-title">Voice Designer</h1>
<p class="studucate-subtitle">Type something, hear it in Stu's voice.</p>
"""

STU_WIDGET_HTML = f"""
<div id="stu-widget">
	<div id="stu-bubble">Hi, I'm Stu!</div>
	<img id="stu-avatar" src="{STU_URI}" alt="Stu, the Studucate mascot" />
</div>
"""

CUSTOM_CSS = """
.studucate-brand {
	display: inline-flex;
	align-items: center;
	background: #ffffff;
	border: 1px solid #e4e1db;
	border-radius: 12px;
	padding: 8px 16px;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
	margin-bottom: 12px;
}
.studucate-brand img { height: 36px; display: block; }
.studucate-title { margin: 0 0 4px; font-size: 1.4rem; font-weight: 600; }
.studucate-subtitle { margin: 0 0 8px; color: #726d63; }

#stu-widget {
	position: fixed;
	right: 20px;
	bottom: 20px;
	z-index: 999;
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	gap: 8px;
	animation: stu-enter 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both;
	animation-delay: 0.2s;
}
@keyframes stu-enter {
	from { opacity: 0; transform: translateX(50px) scale(0.6); }
	to { opacity: 1; transform: translateX(0) scale(1); }
}
#stu-bubble {
	background: #ffffff;
	border: 1px solid #e4e1db;
	border-radius: 12px;
	padding: 8px 12px;
	font-size: 0.82rem;
	color: #1c1b19;
	box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
	max-width: 170px;
	opacity: 0;
	transform: translateY(6px) scale(0.95);
	animation: stu-bubble-peek 5s ease both;
	animation-delay: 1s;
}
@keyframes stu-bubble-peek {
	0%, 100% { opacity: 0; transform: translateY(6px) scale(0.95); }
	15%, 65% { opacity: 1; transform: translateY(0) scale(1); }
}
#stu-avatar {
	width: 64px;
	height: 64px;
	border-radius: 50%;
	object-fit: cover;
	object-position: top center;
	background: #e4e1db;
	box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
	transform-origin: 68% 85%;
	animation: stu-idle-wave 6s ease-in-out infinite;
	animation-delay: 0.9s;
}
@keyframes stu-idle-wave {
	0%, 20%, 100% { transform: rotate(0deg); }
	2% { transform: rotate(-9deg); }
	4% { transform: rotate(15deg); }
	6% { transform: rotate(-11deg); }
	8% { transform: rotate(9deg); }
	10% { transform: rotate(-5deg); }
	12% { transform: rotate(0deg); }
}
"""

with gr.Blocks(title="Studucate Voice Designer") as demo:
	gr.HTML(HEADER_HTML)

	text_input = gr.Textbox(
		show_label=False,
		placeholder="Type or paste the text you want spoken...",
		lines=6,
		max_lines=14,
		max_length=MAX_CHARS,
	)
	generate_btn = gr.Button("Generate", variant="primary")

	version_state = gr.State(0)

	with gr.Row():
		gr.Markdown("### Recent generations")
		clear_btn = gr.Button("Clear", size="sm")

	@gr.render(inputs=[version_state])
	def render_history(_version):
		history = load_history()
		if not history:
			gr.Markdown("_Generated clips will show up here, ready to play and download._")
			return
		for record in reversed(history):
			gr.Audio(
				value=record["path"],
				label=record["text"][:80],
				type="filepath",
				buttons=["download"],
				interactive=False,
			)

	gr.HTML(STU_WIDGET_HTML)

	generate_btn.click(
		generate,
		inputs=[text_input, version_state],
		outputs=[text_input, version_state],
	)
	clear_btn.click(clear_history, inputs=[version_state], outputs=[version_state])


if __name__ == "__main__":
	demo.queue().launch(
		server_name=os.environ.get("HOST", "0.0.0.0"),
		server_port=int(os.environ.get("PORT", 7860)),
		css=CUSTOM_CSS,
	)
