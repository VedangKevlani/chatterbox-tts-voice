FROM python:3.12-slim

# ffmpeg on Debian ships with librubberband support, which the pitch-shift
# step in tts_engine.py depends on.
RUN apt-get update && apt-get install -y --no-install-recommends \
	ffmpeg \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# CPU-only torch/torchaudio wheels are a fraction of the size of the
# default CUDA-bundled ones and this app never uses a GPU.
RUN pip install --no-cache-dir torch==2.6.0 torchaudio==2.6.0 \
	--index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir .

# HF Spaces / most container platforms run the app as a non-root user.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser
ENV HOST=0.0.0.0
ENV PORT=7860

EXPOSE 7860
CMD ["python", "server.py"]
