---
title: Studucate Voice Designer
emoji: 🎙️
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: "6.8.0"
app_file: gradio_app.py
pinned: false
---

# Studucate Voice Designer

A small web app for turning text into speech in Stu's voice, built on
[Chatterbox](https://github.com/resemble-ai/chatterbox) (Turbo model).
Type text, generate audio, play it back, download it, and revisit past
generations.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [ffmpeg](https://ffmpeg.org/download.html) on your `PATH`, built with
  `librubberband` support (used for the reference-voice pitch shift)

## Setup

```bash
git clone https://github.com/VedangKevlani/chatterbox-tts-voice.git
cd chatterbox-tts-voice
uv sync
```

`uv sync` installs everything from `pyproject.toml` / `uv.lock`,
including `torch` and `transformers` — this step downloads several GB
and can take a while.

## Running locally

```bash
uv run python server.py
```

Then open `http://127.0.0.1:7860`.

On first run, the server downloads the Chatterbox Turbo checkpoint
from Hugging Face (cached afterward in `~/.cache/huggingface`) and
loads the model into memory before it can serve generations — this can
take a couple of minutes. The page itself loads immediately; only the
first "Generate" click waits on warmup if it hasn't finished yet.

## How it works

- `tts_engine.py` — voice cloning, text chunking, and generation logic
  (see `CLAUDE.md` for the specific voice/model settings and why
  they're set the way they are)
- `server.py` — Flask backend: runs each generation as a background
  job so the UI can poll progress, and persists a small history of past
  generations to `outputs/history.json`
- `static/` — the custom frontend used by `server.py` (plain HTML/CSS/JS,
  no build step) — this is what you run locally
- `gradio_app.py` — a separate entry point for the deployed version (see
  Deployment below); same `tts_engine.py`, adapted to Gradio's component
  model instead of the custom UI
- `app.py` — a one-off CLI script using the same engine, for quick
  testing outside either web UI

## Notes

- Generation is CPU-bound and can take minutes for longer text — it's
  chunked into ~25-word pieces to avoid quality degrading near
  Chatterbox's generation length cap (see `CLAUDE.md`).
- `outputs/` (generated audio + history) is gitignored — it's runtime
  data, not source.

## Deployment (Hugging Face Spaces)

This app needs a real, persistent process with a few GB of RAM to hold
the model — it does **not** fit serverless platforms (Vercel) or
free-tier hosts with ~512MB RAM (Render's free/Starter tiers). Hugging
Face Spaces' free CPU tier (16GB RAM) is a good fit.

Spaces' **Docker** SDK now requires a verified payment method on file
even for free hardware, so deployment uses the **Gradio** SDK instead
(no card required) via `gradio_app.py` — a separate entry point that
reuses `tts_engine.py` but rebuilds the UI in Gradio's component model
(native progress bar, audio player, and download button) instead of
the custom Flask/HTML frontend. Local development is unaffected; keep
using `server.py` as described above.

1. Create a new Space at <https://huggingface.co/new-space> with
   **SDK: Gradio** and **Hardware: CPU Basic (free)**. Note the git
   URL it gives you (`https://huggingface.co/spaces/<you>/<space-name>`).
2. Add it as a second git remote alongside GitHub and push:
   ```bash
   git remote add space https://huggingface.co/spaces/<you>/<space-name>
   git push space main
   ```
3. The Space reads `app_file: gradio_app.py` from this README's
   frontmatter and runs it directly — no Dockerfile involved.
4. First run downloads the model checkpoint from Hugging Face and
   loads it into memory — expect the Space, and the first "Generate"
   click, to take a few minutes before responding the first time.

### Keeping it awake (UptimeRobot)

Free Spaces go to sleep after a period of inactivity, which means the
next visitor eats a slow cold start (model reload). To avoid that,
set up a free [UptimeRobot](https://uptimerobot.com) HTTP(s) monitor:

- URL: `https://<you>-<space-name>.hf.space/` (the Space's root page)
- Interval: every 5 minutes
- A plain page load is enough to register as activity and doesn't
  trigger a generation or add real load.
