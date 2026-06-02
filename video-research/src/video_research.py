#!/usr/bin/env python3
"""Video research workflow CLI.

Fetches a YouTube transcript when captions are available, optionally falls back
through local audio download/transcription, and writes research artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse


@dataclass
class TranscriptResult:
    video_id: str
    title: str
    duration: str
    transcript: str
    source: str
    raw: dict


def extract_video_id(value: str) -> str:
    """Extract an 11-character YouTube video ID from common URL forms."""
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    parsed = urlparse(value)
    if parsed.netloc.endswith("youtu.be"):
        candidate = parsed.path.strip("/").split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
                return candidate
        parts = [p for p in parsed.path.split("/") if p]
        for marker in ("embed", "shorts", "live"):
            if marker in parts:
                idx = parts.index(marker)
                if idx + 1 < len(parts) and re.fullmatch(r"[A-Za-z0-9_-]{11}", parts[idx + 1]):
                    return parts[idx + 1]
    raise ValueError(f"Could not extract a YouTube video ID from: {value}")


def format_timestamp(seconds: float | int) -> str:
    total = int(float(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _segment_value(seg: object, key: str, default: object = "") -> object:
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def _coalesce_segments(segments: Iterable[object]) -> str:
    lines: list[str] = []
    for seg in segments:
        start = _segment_value(seg, "start", 0)
        text = " ".join(str(_segment_value(seg, "text", "")).replace("\n", " ").split())
        if text:
            lines.append(f"{format_timestamp(float(start))} {text}")
    return "\n".join(lines)


def fetch_youtube_transcript(url: str, languages: list[str] | None = None) -> TranscriptResult:
    """Fetch captions via youtube-transcript-api and metadata via yt-dlp if available."""
    video_id = extract_video_id(url)
    languages = languages or ["en"]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("youtube-transcript-api is not installed") from exc

    api = YouTubeTranscriptApi()
    fetched = None
    errors: list[str] = []
    for lang in languages:
        try:
            fetched = api.fetch(video_id, languages=[lang])
            break
        except Exception as exc:  # pragma: no cover - API dependent
            errors.append(f"{lang}: {exc}")
    if fetched is None:
        try:
            fetched = api.fetch(video_id)
        except Exception as exc:  # pragma: no cover - API dependent
            joined = "\n".join(errors + [str(exc)])
            raise RuntimeError(f"No YouTube transcript available. {joined}") from exc

    raw_segments = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else list(fetched)
    transcript = _coalesce_segments(raw_segments)
    title = video_id
    duration = "unknown"
    metadata = get_video_metadata(url)
    if metadata:
        title = metadata.get("title") or title
        if metadata.get("duration") is not None:
            duration = format_timestamp(metadata["duration"])
    return TranscriptResult(video_id, title, duration, transcript, "youtube-captions", {"segments": raw_segments, "metadata": metadata})


def get_video_metadata(url: str) -> dict:
    cmd = [sys.executable, "-m", "yt_dlp", "--skip-download", "--dump-single-json", url]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        return json.loads(proc.stdout)
    except Exception:
        return {}


def transcribe_audio_fallback(url: str, out_dir: Path, stt_python: str = "/home/jason/.embody-stt/bin/python") -> TranscriptResult:
    """Download audio with yt-dlp and transcribe using local faster-whisper."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for audio fallback")
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_template = str(out_dir / "audio.%(ext)s")
    cmd = [sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "wav", "-o", audio_template, url]
    subprocess.run(cmd, check=True)
    wavs = sorted(out_dir.glob("audio*.wav"))
    if not wavs:
        raise RuntimeError("yt-dlp did not produce a WAV file")
    stt = Path(stt_python)
    if not stt.exists():
        raise RuntimeError(f"faster-whisper Python not found: {stt_python}")
    script = out_dir / "_transcribe.py"
    script.write_text(
        "from faster_whisper import WhisperModel\n"
        "import sys\n"
        "model=WhisperModel('base', device='cpu', compute_type='int8')\n"
        "segments, info=model.transcribe(sys.argv[1], beam_size=5)\n"
        "for s in segments:\n"
        " print(f'{int(s.start)//60}:{int(s.start)%60:02d} {s.text.strip()}')\n",
        encoding="utf-8",
    )
    proc = subprocess.run([str(stt), str(script), str(wavs[0])], check=True, capture_output=True, text=True)
    video_id = extract_video_id(url)
    metadata = get_video_metadata(url)
    return TranscriptResult(
        video_id=video_id,
        title=metadata.get("title") or video_id,
        duration=format_timestamp(metadata.get("duration", 0)) if metadata.get("duration") else "unknown",
        transcript=proc.stdout.strip(),
        source="local-faster-whisper",
        raw={"metadata": metadata},
    )


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lower = text.lower()
    return any(n.lower() in lower for n in needles)


def _select_lines(transcript: str, needles: Iterable[str], limit: int = 6) -> list[str]:
    selected = [line for line in transcript.splitlines() if _contains_any(line, needles)]
    return selected[:limit]


def build_brief(transcript: str, url: str, title: str, video_id: str) -> str:
    agent_lines = _select_lines(transcript, ["agent", "harness", "tool", "orchestration", "memory", "storage"])
    system_lines = _select_lines(transcript, ["vera", "rubin", "cpu", "bluefield", "ai factory", "liquid", "fabric"])
    pc_lines = _select_lines(transcript, ["spark", "pc", "unified memory", "trillion", "r2-d2", "c3po"])
    physical_lines = _select_lines(transcript, ["cosmos", "physical ai", "robot", "hyperion", "isaac", "humanoid"])

    def bullets(lines: list[str]) -> str:
        if not lines:
            return "- No direct timestamped hits found in this transcript slice."
        return "\n".join(f"- {line}" for line in lines)

    return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
Jensen is describing a platform shift: applications become agent harnesses, infrastructure becomes AI factories, PCs become local agent computers, and robotics becomes the physical-world extension of the same pattern.

## Why this matters for Jason
- Agent systems are being framed as the next application pattern: LLM(s) plus a harness that manages orchestration, tools, databases, storage, and output.
- Hardware is being redesigned around the agentic loop, not just around human UI workloads.
- Memory/storage bandwidth and CPU orchestration become first-class AppSec and SAST concerns because agents will operate over large codebases, toolchains, and enterprise data.
- The same reference-platform idea spans cloud agents, desktop agents, autonomous vehicles, and humanoid robots — useful for thinking about Keelpin, Hermes, and physical Minnie as one continuum.

## Key evidence — agent harness / application pattern
{bullets(agent_lines)}

## Key evidence — hardware harnesses software
{bullets(system_lines)}

## Key evidence — agent PC / local workstation direction
{bullets(pc_lines)}

## Key evidence — physical AI / robotics continuum
{bullets(physical_lines)}

## Research implications
1. Treat the harness as the product surface: permissions, tool routing, memory, provenance, and observability are where enterprise value and risk concentrate.
2. Track CPUs/storage/fabrics built for agent orchestration, because performance bottlenecks move from model inference alone into context movement and tool coordination.
3. Expect local agent workstations with very large unified memory to change developer workflows: private models, local code reasoning, local security scanning, and always-on assistants become practical.
4. Robotics and physical AI are using the same stack pattern: open models, simulation/data generation, runtime OS, and reference computers.

## Follow-up questions
- What does an AppSec/SAST harness need to log when an agent writes code or calls tools?
- How should Keelpin model agent-created code provenance and tool-use traces inside Joern/Argus workflows?
- Which workloads should stay local on agent PCs versus run in AI factories?
- What hardware counters or traces would reveal bottlenecks in agent orchestration loops?
"""


def write_artifacts(result: TranscriptResult, out_dir: Path, source_url: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / "transcript_timestamped.txt"
    json_path = out_dir / "transcript.json"
    brief_path = out_dir / "brief.md"
    transcript_path.write_text(result.transcript + "\n", encoding="utf-8")
    json_path.write_text(json.dumps({
        "video_id": result.video_id,
        "title": result.title,
        "duration": result.duration,
        "source": result.source,
        "url": source_url,
        "raw": result.raw,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    brief_path.write_text(build_brief(result.transcript, source_url, result.title, result.video_id), encoding="utf-8")
    return {"transcript": transcript_path, "json": json_path, "brief": brief_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract YouTube video research artifacts in one shot.")
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--out", default=None, help="Output directory; default: ./video-research-output/<video_id>")
    parser.add_argument("--language", action="append", default=["en"], help="Caption language preference; repeatable")
    parser.add_argument("--fallback-audio", action="store_true", help="If captions fail, download audio and transcribe with local faster-whisper")
    args = parser.parse_args(argv)

    video_id = extract_video_id(args.url)
    out_dir = Path(args.out) if args.out else Path("video-research-output") / video_id
    try:
        result = fetch_youtube_transcript(args.url, languages=args.language)
    except Exception as exc:
        if not args.fallback_audio:
            print(f"Caption fetch failed: {exc}", file=sys.stderr)
            return 2
        result = transcribe_audio_fallback(args.url, out_dir)
    paths = write_artifacts(result, out_dir, args.url)
    print(f"title: {result.title}")
    print(f"duration: {result.duration}")
    print(f"source: {result.source}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
