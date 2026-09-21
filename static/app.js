const textInput = document.getElementById("text-input");
const wordCount = document.getElementById("word-count");
const generateBtn = document.getElementById("generate-btn");
const errorMessage = document.getElementById("error-message");
const resultsList = document.getElementById("results-list");
const resultsHeader = document.getElementById("results-header");
const clearHistoryBtn = document.getElementById("clear-history-btn");
const emptyState = document.getElementById("empty-state");
const loadingHistory = document.getElementById("loading-history");
const progress = document.getElementById("progress");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const themeToggle = document.getElementById("theme-toggle");
const iconSun = themeToggle.querySelector(".icon-sun");
const iconMoon = themeToggle.querySelector(".icon-moon");
const stuAvatarBtn = document.getElementById("stu-avatar-btn");

stuAvatarBtn.addEventListener("click", () => {
	stuAvatarBtn.classList.remove("stu-widget__avatar--pulse");
	// eslint-disable-next-line no-unused-expressions
	stuAvatarBtn.offsetWidth; // force reflow so the animation can restart
	stuAvatarBtn.classList.add("stu-widget__avatar--pulse");
});
stuAvatarBtn.addEventListener("animationend", (e) => {
	if (e.animationName === "stu-click-wave") {
		stuAvatarBtn.classList.remove("stu-widget__avatar--pulse");
	}
});

const THEME_KEY = "studucate-theme";

function applyTheme(theme) {
	document.documentElement.setAttribute("data-theme", theme);
	iconSun.hidden = theme === "dark";
	iconMoon.hidden = theme !== "dark";
	themeToggle.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
}

function initTheme() {
	let stored = null;
	try {
		stored = localStorage.getItem(THEME_KEY);
	} catch (err) {
		// Storage unavailable (private mode, etc.) - fall back to system preference.
	}
	const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
	applyTheme(stored || systemTheme);
}

themeToggle.addEventListener("click", () => {
	const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
	applyTheme(next);
	try {
		localStorage.setItem(THEME_KEY, next);
	} catch (err) {
		// Ignore - theme just won't persist across reloads.
	}
});

initTheme();

const POLL_INTERVAL_MS = 700;

function countWords(text) {
	const trimmed = text.trim();
	return trimmed ? trimmed.split(/\s+/).length : 0;
}

function updateWordCount() {
	const words = countWords(textInput.value);
	wordCount.textContent = `${words} word${words === 1 ? "" : "s"}`;
}

function setLoading(loading) {
	generateBtn.disabled = loading;
	generateBtn.classList.toggle("btn--loading", loading);
}

function showError(message) {
	errorMessage.textContent = message;
	errorMessage.hidden = false;
}

function clearError() {
	errorMessage.hidden = true;
	errorMessage.textContent = "";
}

function showProgress() {
	progress.hidden = false;
	progressBar.classList.add("progress__bar--indeterminate");
	progressBar.style.width = "";
	progressLabel.textContent = "Generating...";
}

function updateProgress(completed, total) {
	if (!total) {
		return;
	}
	const percent = Math.round((completed / total) * 100);
	progressBar.classList.remove("progress__bar--indeterminate");
	progressBar.style.width = `${percent}%`;
	progressLabel.textContent = `${percent}% - part ${completed} of ${total}`;
}

function hideProgress() {
	progress.hidden = true;
}

function escapeHtml(str) {
	const div = document.createElement("div");
	div.textContent = str;
	return div.innerHTML;
}

const ICON_PLAY = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4l14 8-14 8V4z"/></svg>';
const ICON_PAUSE = '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
const ICON_VOLUME = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 9v6h4l5 5V4L8 9H4z"/><path d="M16.5 8.5a5 5 0 010 7" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg>';
const ICON_MUTED = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 9v6h4l5 5V4L8 9H4z"/><path d="M16 9l5 6M21 9l-5 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

function formatTime(seconds) {
	if (!isFinite(seconds) || seconds < 0) {
		return "0:00";
	}
	const mins = Math.floor(seconds / 60);
	const secs = Math.floor(seconds % 60);
	return `${mins}:${String(secs).padStart(2, "0")}`;
}

function slugify(text) {
	const words = text.trim().split(/\s+/).slice(0, 6).join(" ");
	const slug = words.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-+|-+$)/g, "");
	return slug || "chatterbox-clip";
}

async function downloadClip(url, suggestedName) {
	const input = window.prompt("Save as", suggestedName);
	if (!input) {
		return;
	}
	const filename = input.toLowerCase().endsWith(".mp3") ? input : `${input}.mp3`;

	if (window.showSaveFilePicker) {
		try {
			const handle = await window.showSaveFilePicker({
				suggestedName: filename,
				types: [{ description: "MP3 audio", accept: { "audio/mpeg": [".mp3"] } }],
			});
			const response = await fetch(url);
			const blob = await response.blob();
			const writable = await handle.createWritable();
			await writable.write(blob);
			await writable.close();
			return;
		} catch (err) {
			if (err.name === "AbortError") {
				return;
			}
			// Fall through to the plain-download fallback below.
		}
	}

	const a = document.createElement("a");
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
}

function initPlayer(card, url) {
	const audio = card.querySelector(".player__audio");
	const toggleBtn = card.querySelector(".player__toggle");
	const seek = card.querySelector(".player__seek");
	const timeLabel = card.querySelector(".player__time");
	const speed = card.querySelector(".player__speed");
	const muteBtn = card.querySelector(".player__mute");
	const volume = card.querySelector(".player__volume");
	let scrubbing = false;

	function setPlayIcon(playing) {
		toggleBtn.innerHTML = playing ? ICON_PAUSE : ICON_PLAY;
		toggleBtn.setAttribute("aria-label", playing ? "Pause" : "Play");
	}

	toggleBtn.addEventListener("click", () => {
		if (audio.paused) {
			audio.play().catch((err) => {
				showError(`Couldn't play this clip: ${err.message}`);
			});
		} else {
			audio.pause();
		}
	});

	audio.addEventListener("play", () => setPlayIcon(true));
	audio.addEventListener("pause", () => setPlayIcon(false));
	audio.addEventListener("ended", () => setPlayIcon(false));

	audio.addEventListener("loadedmetadata", () => {
		seek.max = audio.duration;
		timeLabel.textContent = `0:00 / ${formatTime(audio.duration)}`;
	});

	audio.addEventListener("timeupdate", () => {
		if (!scrubbing) {
			seek.value = audio.currentTime;
		}
		timeLabel.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
	});

	seek.addEventListener("input", () => {
		scrubbing = true;
		timeLabel.textContent = `${formatTime(seek.value)} / ${formatTime(audio.duration)}`;
	});
	seek.addEventListener("change", () => {
		audio.currentTime = seek.value;
		scrubbing = false;
	});

	speed.addEventListener("change", () => {
		audio.playbackRate = parseFloat(speed.value);
	});

	volume.addEventListener("input", () => {
		audio.volume = parseFloat(volume.value);
		audio.muted = audio.volume === 0;
		muteBtn.innerHTML = audio.muted ? ICON_MUTED : ICON_VOLUME;
	});

	muteBtn.addEventListener("click", () => {
		audio.muted = !audio.muted;
		muteBtn.innerHTML = audio.muted ? ICON_MUTED : ICON_VOLUME;
		if (!audio.muted && audio.volume === 0) {
			audio.volume = 1;
			volume.value = 1;
		}
	});
}

function addResult({ url, text }) {
	resultsHeader.hidden = false;
	emptyState.hidden = true;

	const li = document.createElement("li");
	li.className = "result-card";

	li.innerHTML = `
		<div class="player">
			<button class="icon-btn player__toggle" type="button" aria-label="Play">${ICON_PLAY}</button>
			<div class="player__main">
				<input type="range" class="player__seek" min="0" max="0" value="0" step="0.01" />
				<div class="player__meta">
					<span class="player__time">0:00 / 0:00</span>
					<div class="player__right">
						<select class="player__speed" aria-label="Playback speed">
							<option value="0.5">0.5x</option>
							<option value="0.75">0.75x</option>
							<option value="1" selected>1x</option>
							<option value="1.25">1.25x</option>
							<option value="1.5">1.5x</option>
							<option value="2">2x</option>
						</select>
						<button class="icon-btn player__mute" type="button" aria-label="Mute">${ICON_VOLUME}</button>
						<input type="range" class="player__volume" min="0" max="1" step="0.05" value="1" />
					</div>
				</div>
			</div>
			<audio class="player__audio" preload="metadata" src="${url}"></audio>
		</div>
		<p class="result-card__text">${escapeHtml(text)}</p>
		<div class="result-card__footer">
			<button class="btn btn--ghost result-card__download" type="button">Download</button>
		</div>
	`;

	li.querySelector(".result-card__download").addEventListener("click", () => {
		downloadClip(url, `${slugify(text)}.mp3`);
	});

	resultsList.prepend(li);
	initPlayer(li, url);
}

function pollJob(jobId, text) {
	return new Promise((resolve, reject) => {
		const timer = setInterval(async () => {
			try {
				const response = await fetch(`/api/generate/${jobId}`);
				const job = await response.json();

				if (!response.ok) {
					throw new Error(job.error || "Something went wrong.");
				}

				updateProgress(job.completed, job.total);

				if (job.status === "done") {
					clearInterval(timer);
					resolve({ url: job.url, text });
				} else if (job.status === "error") {
					clearInterval(timer);
					reject(new Error(job.error || "Generation failed."));
				}
			} catch (err) {
				clearInterval(timer);
				reject(err);
			}
		}, POLL_INTERVAL_MS);
	});
}

async function generate() {
	const text = textInput.value.trim();
	clearError();

	if (!text) {
		showError("Enter some text first.");
		return;
	}

	setLoading(true);
	showProgress();
	try {
		const response = await fetch("/api/generate", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text }),
		});
		const data = await response.json();

		if (!response.ok) {
			throw new Error(data.error || "Something went wrong.");
		}

		const result = await pollJob(data.job_id, text);
		addResult(result);
		textInput.value = "";
		updateWordCount();
	} catch (err) {
		showError(err.message);
	} finally {
		setLoading(false);
		hideProgress();
	}
}

textInput.addEventListener("input", updateWordCount);
generateBtn.addEventListener("click", generate);
textInput.addEventListener("keydown", (e) => {
	if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
		generate();
	}
});

clearHistoryBtn.addEventListener("click", async () => {
	if (!window.confirm("Delete all saved generations? This can't be undone.")) {
		return;
	}
	try {
		const response = await fetch("/api/history", { method: "DELETE" });
		if (!response.ok) {
			const data = await response.json().catch(() => ({}));
			throw new Error(data.error || "Couldn't clear history.");
		}
		resultsList.innerHTML = "";
		resultsHeader.hidden = true;
		emptyState.hidden = false;
	} catch (err) {
		showError(err.message);
	}
});

async function loadHistory() {
	try {
		const response = await fetch("/api/history");
		const history = await response.json();
		history.forEach((item) => addResult({ url: item.url, text: item.text }));
	} catch (err) {
		// History is a nice-to-have; ignore failures.
	} finally {
		loadingHistory.hidden = true;
		if (resultsList.children.length === 0) {
			emptyState.hidden = false;
		}
	}
}

loadHistory();
