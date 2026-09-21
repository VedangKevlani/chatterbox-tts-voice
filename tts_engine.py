import os
import re
import subprocess
import tempfile
import threading

import soundfile as sf
import torch
from chatterbox.tts_turbo import ChatterboxTurboTTS

# See CLAUDE.md "Voice settings (locked)" - do not change these without an
# explicit request. This module is the single source of truth for the
# cloning/generation pipeline; app.py and server.py both call into it.
REFERENCE_AUDIO = "male_voice.mp3"
PITCH_SHIFT_SEMITONES = 1


def build_reference_wav(source_path=REFERENCE_AUDIO):
	pitch_factor = 2 ** (PITCH_SHIFT_SEMITONES / 12)
	reference_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
	subprocess.run(
		[
			"ffmpeg", "-y", "-i", source_path,
			"-af", (
				"equalizer=f=1100:t=q:w=2.5:g=-8,treble=g=3:f=6000,"
				f"rubberband=pitch={pitch_factor}:formant=preserved,"
				"loudnorm=I=-27:TP=-2:LRA=7"
			),
			"-ar", "24000", "-ac", "1", reference_wav,
		],
		check=True,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
	)
	return reference_wav


def chunk_text(text, max_words=25):
	# Any generation whose text exceeds ~25 words gets chunked on sentence
	# boundaries, to stay clear of Turbo's 1000-token cap where pacing/quality
	# degrade. See CLAUDE.md "Chunking long generations".
	sentences = re.split(r"(?<=[.!?])\s+", text.strip())
	chunks, current, current_words = [], [], 0
	for sentence in sentences:
		words = len(sentence.split())
		if current and current_words + words > max_words:
			chunks.append(" ".join(current))
			current, current_words = [sentence], words
		else:
			current.append(sentence)
			current_words += words
	if current:
		chunks.append(" ".join(current))
	return chunks


class TTSEngine:
	"""Lazily loads the model + reference conditioning once, then serializes
	generations behind a lock (the underlying model isn't safe for concurrent
	calls)."""

	def __init__(self):
		self._lock = threading.Lock()
		self._model = None
		self._reference_wav = None

	def ensure_loaded(self):
		if self._model is not None:
			return
		with self._lock:
			if self._model is not None:
				return
			self._reference_wav = build_reference_wav()
			model = ChatterboxTurboTTS.from_pretrained(device="cpu")
			model.prepare_conditionals(self._reference_wav, norm_loudness=True)
			self._model = model

	def generate_to_file(self, text, output_path, on_progress=None):
		"""on_progress(done, total), called after each chunk finishes generating."""
		self.ensure_loaded()
		with self._lock:
			model = self._model
			chunks = chunk_text(text)
			silence = torch.zeros(1, int(0.25 * model.sr))
			chunk_wavs = []
			for i, chunk in enumerate(chunks):
				chunk_wavs.append(model.generate(chunk, temperature=0.8))
				chunk_wavs.append(silence)
				if on_progress:
					on_progress(i + 1, len(chunks))
			wav = torch.cat(chunk_wavs[:-1], dim=1)

			wav_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
			try:
				sf.write(wav_path, wav.squeeze().detach().cpu().numpy(), model.sr)
				subprocess.run(
					["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "2", output_path],
					check=True,
					stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL,
				)
			finally:
				os.unlink(wav_path)
