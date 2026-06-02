# Video Research CLI

Give this README to your AI agent. It explains how to install and use this CLI.

## What this is

`video-research` turns a YouTube video into research artifacts in one shot:

- fetch YouTube captions/transcript when available;
- optionally fall back to downloading audio and transcribing locally with `faster-whisper`;
- write a timestamped transcript;
- write metadata JSON;
- write per-video catalogue metadata (`metadata.json`) with category, tags, and relevance lanes;
- write/update a batch collection index (`_index.json`) under the output root;
- write/update a morning-show source digest (`_morning_sources.md`) so Evy's Morning AI Brief can treat ingested videos as first-class source material;
- write/update an Obsidian-native catalogue page (`Video Research Catalogue.md`) listing video title, URL, short description, date of video, and date ingested;
- write a first-pass research brief specialized for known agent-research categories: NVIDIA/hardware-harness talks, agent auth/auth.md, agent lifecycle/LangSmith, future agent architecture, open-model evaluation, local AI workspaces, dynamic agent workflows, AI-era judgment/evidence, interpretable context methodology, IDE-native coding harnesses, desktop personal agents, source-grounded research notebooks, codebase comprehension agents, codebase knowledge graph comparisons, AI sales automation workflows, and frontier model signal watch.

This is designed for Jason/Evy research ingestion: give Evy a video URL, get the source material and a brief quickly, then refine the brief with LLM analysis.

## Requirements

- Python 3.11+
- `ffmpeg` for audio fallback
- Python packages in `requirements.txt`:
  - `youtube-transcript-api`
  - `yt-dlp`

Optional fallback:

- local faster-whisper environment at `/home/jason/.embody-stt/bin/python` or edit the path in `src/video_research.py`.

## Install

From this folder:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Or run with an existing venv that has the dependencies installed.

## Configure

No secrets are required. Do not commit downloaded video/audio, transcripts from private sources, `.env` files, cookies, or API keys.

## Verify installation

```bash
python3 -m unittest discover -s tests -v
src/video-research --help
```

Expected: all tests pass and the CLI prints usage/help text.

## Usage

Captions-only path for one video:

```bash
src/video-research 'https://youtu.be/O8jg-Shxd3o?si=4HBg7cvAXHPoU8i5' --out ./output/O8jg-Shxd3o
```

Batch path for multiple videos; each video writes under `./output/<video_id>/`:

```bash
src/video-research \
  'https://youtu.be/R9K2574YEAg?si=01kPnAaRQvYYAx_T' \
  'https://youtu.be/p6Npi-HBoRU?si=XiLUx03ZQTIqNffb' \
  --out-root ./output
```

With local audio transcription fallback if captions are unavailable:

```bash
src/video-research 'https://youtu.be/VIDEO_ID' --fallback-audio --out ./output/VIDEO_ID
```

Outputs:

```text
output/VIDEO_ID/
  transcript_timestamped.txt
  transcript.json
  brief.md
  metadata.json
output/_index.json
output/_morning_sources.md
output/Video Research Catalogue.md
```

### Categorization and tags

Each `metadata.json` contains:

- `category`: primary shelf for the video.
- `tags`: searchable cross-cutting labels such as `notebooklm`, `codebase-analysis`, `openhuman`, `workflow-automation`, or `frontier-models`.
- `relevance_lanes`: Jason-facing reason-to-care lanes such as `hermes-evy`, `keelpin-appsec`, `provenance`, `local-models`, `model-watch`, `workflow-automation`, or `competitive-reference`.

The batch `_index.json` rolls up all per-video metadata under the output root and lists all videos, categories, tags, and relevance lanes. Use it to answer “what have we collected about X?” without rereading every brief.

`_morning_sources.md` is a ranked Markdown digest intended for Evy's Morning AI Brief. It preserves source URLs, categories, tags, relevance lanes, and brief artifact paths so the show builder can consider ingested video research alongside web/news/repo/paper sources.

`Video Research Catalogue.md` is Obsidian-native human-facing catalogue page. It indexes videos Jason shared and Evy ingested with these columns: video title, video URL, short description, date of video, and date ingested. Keep `_index.json` as the machine source of truth; treat the Obsidian page as the readable vault surface.

## AI-agent operating notes

1. First try captions; they are fast and preserve timestamps.
2. If captions fail and Jason wants the video anyway, use `--fallback-audio`.
3. Treat generated `brief.md` as a first-pass research brief, not the final word. Re-read the transcript and refine with domain-specific analysis.
4. Keep provenance: always cite the URL, video ID, transcript source, and timestamps.
5. If the video is unavailable/private or YouTube blocks download, report the exact blocker rather than inventing a transcript.

## Known pitfalls

- Raspberry Pi OS blocks global pip installs due to PEP 668; use a venv.
- YouTube captions can contain recognition errors. Confirm names and product names against the video metadata or source page.
- `yt-dlp` may require updates when YouTube changes extraction behavior.
- Faster-whisper on CPU can be slow for long videos; captions are preferred when available.
- Never use browser cookies or authenticated downloads unless Jason explicitly asks and scope is clear.

## Files

- `src/video-research` — executable wrapper.
- `src/video_research.py` — implementation.
- `tests/test_video_research.py` — unit tests.
- `requirements.txt` — Python dependencies.
