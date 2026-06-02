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


def _is_agent_auth_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in ["auth.md", "auth dot m d", "idjag", "agentic registration"])


def _is_agent_lifecycle_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "agent development lifecycle",
        "langsmith engine",
        "smithdb",
        "build, test, deploy, monitor",
    ])


def _is_future_agent_architecture_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "interrupt 2027",
        "agents of the future",
        "what do the agents of the future look like",
        "two types of agents",
    ])


def _is_open_model_evaluation_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "minimax m3",
        "mini max m3",
        "open source model",
        "opensource ai model",
        "swe-bench",
        "toolbench",
    ])


def _is_local_ai_workspace_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "odyssey s",
        "odysseus",
        "ai workspace",
        "cookbook that scans your hardware",
        "web search and shell access",
        "memory, email, notes, calendar",
    ])


def _is_dynamic_workflows_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "dynamic workflows",
        "claude code dynamic workflows",
        "workflow is claude basically creates a javascript file",
        "workflows are basically claude code writing a script",
        "giant parallel job",
    ])

def _is_ai_judgment_evidence_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "treating ai output as just the beginning",
        "evidence problem",
        "human judgment",
        "age of whiteboards",
        "situation, decision, risk, and change",
        "comprehension over generation",
    ])


def _is_interpretable_context_methodology_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "interpretable context methodology",
        "automating the wrong layer",
        "folders and markdown files",
        "structuring folders",
        "folder context structure",
        "chain of decisions",
    ])


def _is_ide_native_coding_harness_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "oh my pi",
        "oh-my-pi",
        "native lsp",
        "language server protocol",
        "debugger adapter protocol",
        "hash line edits",
    ])


def _is_desktop_personal_agent_talk(transcript: str, title: str) -> bool:
    haystack = f"{title}\n{transcript}".lower()
    return any(marker in haystack for marker in [
        "openhuman",
        "open human",
        "personal ai super intelligence",
        "desktop application just like slack",
        "meeting agent",
        "subconscious loop",
        "118 plus integrations",
    ])


def build_brief(transcript: str, url: str, title: str, video_id: str) -> str:
    def bullets(lines: list[str]) -> str:
        if not lines:
            return "- No direct timestamped hits found in this transcript slice."
        return "\n".join(f"- {line}" for line in lines)

    if _is_agent_auth_talk(transcript, title):
        harness_lines = _select_lines(transcript, ["runtime", "permissions", "isolation", "scoped credentials", "harness", "feedback"])
        registration_lines = _select_lines(transcript, ["agentic registration", "auth.md", "auth dot m d", "legitimate users", "sign up", "register"])
        idjag_lines = _select_lines(transcript, ["IDJAG", "JWT", "issuer", "audience", "access token"])
        strategy_lines = _select_lines(transcript, ["agent ready", "enterprise ready", "API is the UI", "MCP is not enough", "agent economy"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This talk argues that autonomous agents need agent-native registration: a discoverable, auditable way to prove identity, receive scoped tokens, and become legitimate API users without pretending to be humans.

## Why this matters for Jason
- The talk reinforces that the harness is the product: runtime, isolation, permissions, tools, context, feedback loops, and review.
- For Keelpin, agent identity and token scope become code-provenance and AppSec artifacts, not merely auth plumbing.
- For Hermes/Evy, auth.md-style discovery fits the direction of agent-readable CLIs, MCP tools, signed webhooks, scoped credentials, and service delegation.
- Agent-ready is the next enterprise-ready: products that agents cannot discover, register for, and use will be disadvantaged.

## Key evidence — harness requirements
{bullets(harness_lines)}

## Key evidence — agent-native registration / auth.md
{bullets(registration_lines)}

## Key evidence — IDJAG / token exchange
{bullets(idjag_lines)}

## Key evidence — strategic frame
{bullets(strategy_lines)}

## Research implications
1. Model agent identity, token scope, and tool/API calls as first-class provenance edges in Keelpin/Joern/Argus workflows.
2. Lint auth.md-style files for risky identity proofs, over-broad scopes, anonymous signup policy, claim flows, and revocation gaps.
3. Treat APIs, CLIs, MCP servers, llms.txt, and auth.md as the agent-facing UI surface.
4. Build Hermes/Evy service integrations around explicit delegation: Jason identity vs Evy service identity vs anonymous/claimable agent identity.

## Follow-up questions
- How should Keelpin represent an agent-created PR and the credentials used to create it?
- What minimum scopes should an autonomous coding agent receive for deploy, CI, logs, databases, and issue trackers?
- Should Evy-CLI tools publish llms.txt/auth.md-style manifests for agent discovery?
- How does auth.md compare with OAuth device flow, OIDC federation, SPIFFE/SPIRE, and MCP auth?
"""

    if _is_agent_lifecycle_talk(transcript, title):
        build_lines = _select_lines(transcript, ["build", "agent harness", "execution environment", "deep agents", "tools"])
        test_lines = _select_lines(transcript, ["test phase", "datasets", "metrics", "evaluations", "regressing"])
        deploy_lines = _select_lines(transcript, ["production", "durably", "sandboxes", "auth proxy", "deploy"])
        monitor_lines = _select_lines(transcript, ["traces", "observability", "SmithDB", "Langsmith Engine", "monitor"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This talk frames reliable agents as an Agent Development Lifecycle: Build → Test → Deploy → Monitor, with traces at the center and governance/repair loops layered on top.

## Why this matters for Jason
- For Hermes/Evy, this is a concrete operating model for building, validating, deploying, monitoring, and improving agent workflows.
- For Keelpin, agent traces, tool calls, code changes, credentials, eval failures, and deployment events become AppSec/provenance artifacts.
- For infrastructure, SmithDB's object-storage-backed trace architecture is a useful model for durable, searchable agent memory and observability at scale.
- For product design, agents increasingly become users of the observability tools themselves, so fast trace query is agent UX as well as human UX.

## Key evidence — build
{bullets(build_lines)}

## Key evidence — test/evaluate
{bullets(test_lines)}

## Key evidence — deploy/sandbox/govern
{bullets(deploy_lines)}

## Key evidence — monitor/traces/repair
{bullets(monitor_lines)}

## Research implications
1. Treat traces as the behavioral record of agent execution: inputs, decisions, tools, outputs, and failures.
2. Map trace spans into Keelpin-style provenance graphs: tool call → file write → dependency change → test result → PR/deploy event.
3. Keep credentials outside sandboxes when possible; use proxy/delegation patterns to reduce prompt-injection leakage risk.
4. Build eval datasets from observed production failures so fixes become regression tests instead of one-off prompt tweaks.
5. Consider an Evy Engine-style watchdog that scans failed runs, stale skills, cron stalls, and trace anomalies.

## Follow-up questions
- What Hermes trace schema should capture tool inputs/outputs, artifact paths, verification status, and user-visible results?
- How should Keelpin index agent traces alongside code/property graphs?
- Which failures should become eval dataset rows versus code changes versus skill/context changes?
- Can Evy's Nook/Railway S3 pattern support durable trace/artifact storage for this lifecycle?
"""

    if _is_future_agent_architecture_talk(transcript, title):
        long_horizon_lines = _select_lines(transcript, ["long horizon", "minutes and hours", "days", "code execution", "planning", "subagents", "multi-agent", "skills"])
        latency_lines = _select_lines(transcript, ["latency", "customer experience", "support", "sales", "brand", "voice", "video"])
        voice_lines = _select_lines(transcript, ["speech to text", "text to speech", "native speech", "native voice", "audio", "voice"])
        trust_lines = _select_lines(transcript, ["trust", "observability", "behaving", "production", "monitor", "evaluate"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is a future agent architecture talk: agents are splitting into long-horizon knowledge workers and latency-sensitive customer/voice agents, while both still depend on a shared harness for tools, memory, observability, and trust.

## Why this matters for Jason
- Hermes/Evy sits directly at the intersection: long-horizon tool work plus low-latency voice/desk companion interaction.
- Keelpin should expect agent software to diverge by operating mode: durable asynchronous agents, interactive voice agents, and hybrid agents each produce different provenance and AppSec traces.
- Voice is not just UX polish; speech-to-speech/native audio models change latency, auditability, transcript provenance, and prompt-injection surface.
- Trust requires observability into how agents behave, not merely final outputs.

## Key evidence — long-horizon agents
{bullets(long_horizon_lines)}

## Key evidence — latency-sensitive / customer-experience agents
{bullets(latency_lines)}

## Key evidence — voice and multimodal interface direction
{bullets(voice_lines)}

## Key evidence — trust / observability
{bullets(trust_lines)}

## Research implications
1. Split agent threat models by operating mode: long-running autonomous worker, low-latency voice agent, and human-in-the-loop hybrid.
2. For Hermes/Evy, keep optimizing both durable delegation and immediate conversational responsiveness; they are different product constraints sharing one memory/tool harness.
3. For Keelpin, preserve timestamps, tool calls, intermediate plans, transcript/audio provenance, and escalation points so future agents can be audited after long runs.
4. Treat native voice models as a new security boundary: audio input, transcription, model action, spoken output, and barge-in all need traceability.

## Follow-up questions
- Which Hermes traces distinguish a voice interaction from a long-horizon delegated task?
- How should Keelpin model agent actions that happen over hours or days with multiple resumptions?
- What observability is needed before Evy can safely run more autonomous background work?
- Should voice-agent safety checks happen before STT, after STT, before tool call, before TTS, or all four?
"""

    if _is_open_model_evaluation_talk(transcript, title):
        model_lines = _select_lines(transcript, ["minimax", "m3", "open source", "opensource", "model", "proprietary"])
        coding_lines = _select_lines(transcript, ["coding", "swe-bench", "large scale coding", "code", "task decomposition"])
        tool_lines = _select_lines(transcript, ["tool use", "toolbench", "tool calls", "agents", "autonomous"])
        cost_lines = _select_lines(transcript, ["cheaper", "cost", "price", "50x", "proprietary", "local"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is an open model evaluation brief: MiniMax M3 is presented as a strong open-weight/open-source contender for long-horizon agent work, coding, and tool use, with major cost and local/private deployment implications.

## Why this matters for Jason
- Jason has enough local infrastructure to make open model evaluation operationally meaningful, not theoretical.
- For Hermes/Evy, strong cheaper models can shift routine tool-use, summarization, and research workflows closer to local/private execution.
- For Keelpin, coding-agent benchmarks matter only if paired with provenance: what the model changed, which tools it used, and whether tests/evals caught regressions.
- Cost/performance claims need reproducible harness tests against Jason-relevant workloads, not just leaderboard trust.

## Key evidence — model positioning
{bullets(model_lines)}

## Key evidence — coding / long-horizon capability
{bullets(coding_lines)}

## Key evidence — agent tool use
{bullets(tool_lines)}

## Key evidence — cost / local-private implications
{bullets(cost_lines)}

## Research implications
1. Build a local/private eval harness for Hermes tasks: YouTube research, codebase inspection, AppSec triage, and brief generation.
2. Evaluate models on tool-call discipline, citation/provenance quality, test-writing behavior, and ability to recover from failed tools.
3. Treat benchmark wins as hypotheses until validated on Keelpin/Hermes workloads with real traces.
4. Track open models that can run on Jason's DGX Spark/private infrastructure for privacy-preserving agent workflows.

## Follow-up questions
- Which Hermes workflows should become the standard open-model eval set?
- Should Keelpin score coding agents by vulnerability avoidance, fix quality, or trace/provenance completeness?
- What is the acceptable latency/cost/privacy tradeoff for Evy's routine research jobs?
- Which model sizes should be tested locally versus via API?
"""

    if _is_local_ai_workspace_talk(transcript, title):
        setup_lines = _select_lines(transcript, ["self-host", "clone", "local interface", "admin", "Ollama", "scan", "download", "serve"])
        workspace_lines = _select_lines(transcript, ["AI workspace", "memory", "email", "notes", "calendar", "library", "documents", "brain"])
        tool_lines = _select_lines(transcript, ["agent", "chat", "web search", "shell access", "commands", "deep research", "compare"])
        local_lines = _select_lines(transcript, ["local models", "Gemma", "Open Router", "Nvidia NIM", "free", "offline", "internet connection"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is a local AI workspace brief: Odysseus/Odyssey S packages self-hosted models, agents, web search, shell access, memory, mail, notes, calendar, deep research, and model-management into one local-first UI.

## Why this matters for Jason
- Hermes/Evy should watch this category closely: it is the same “agent workspace” surface Jason wants, but with different tradeoffs around local models, UI, memory, and tool access.
- The dangerous/useful primitive is web search plus shell access: powerful for research and automation, but it needs explicit scope, provenance, and command audit logs.
- Cookbook-style hardware scanning/model recommendation is relevant to Jason’s DGX/Mac/Pi fleet because local/private model routing should become easy and reproducible.
- For Keelpin, local agent workspaces create a need to scan not only code, but agent configuration, memory, tools, shell permissions, and API provider setup.

## Key evidence — self-hosted setup / model management
{bullets(setup_lines)}

## Key evidence — workspace surface
{bullets(workspace_lines)}

## Key evidence — agent tools / research
{bullets(tool_lines)}

## Key evidence — local/private model direction
{bullets(local_lines)}

## Research implications
1. Treat “local AI workspace” apps as harness competitors: model router, tool permissions, memory, UI, research, and shell all bundled together.
2. Build Hermes/Evy provenance around local tool use: every shell command, search, note/memory read, and generated report should have traceable source context.
3. Evaluate whether cookbook-style model discovery belongs in Evy-CLI for Jason’s private infrastructure.
4. Use Keelpin to reason about workspace risk: over-broad shell access, hidden provider keys, unsafe memory exposure, and unreviewed local automation.

## Follow-up questions
- Which local workspace features should Evy absorb versus merely interoperate with?
- What is the minimum safe permission model for a local agent with shell access?
- Could Evy-CLI grow a model-cookbook command for local model discovery and routing?
- How should Keelpin represent local AI workspace configuration as AppSec input?
"""

    if _is_dynamic_workflows_talk(transcript, title):
        concept_lines = _select_lines(transcript, ["dynamic workflows", "JavaScript file", "script", "many agents", "saved", "re-ran"])
        comparison_lines = _select_lines(transcript, ["skills", "sub-agents", "agent teams", "goal", "depth versus width", "width play"])
        cost_lines = _select_lines(transcript, ["tokens", "expensive", "full Claude call", "session limit", "burn money", "Haiku"])
        guardrail_lines = _select_lines(transcript, ["bound the scope", "name the deliverable", "explicit", "criteria", "workflow", "permissions", "global"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is a dynamic workflows brief: Claude Code workflows turn one request into a generated script that fans out many agents horizontally, then merges results, making them useful for wide parallel jobs but risky for token spend, scope control, and artifact placement.

## Why this matters for Jason
- Hermes already has a safer analog in `delegate_task` plus cron/jobs/skills; this talk helps sharpen when to use width-based parallelism versus depth-based goal loops.
- The “script that runs agents” pattern is exactly why workflow artifacts, working directories, and generated plans must be visible and versioned.
- For Keelpin, dynamic workflows are provenance-heavy: every worker, model, tool call, token/cost footprint, and synthesized claim should be traceable.
- The key operational rule is: bound the scope, name the deliverable, set model/cost limits, and choose the right lane: skill, subagent, team, goal, or workflow.

## Key evidence — what dynamic workflows are
{bullets(concept_lines)}

## Key evidence — skills/subagents/teams/goals comparison
{bullets(comparison_lines)}

## Key evidence — token/cost risks
{bullets(cost_lines)}

## Key evidence — guardrails / artifact placement
{bullets(guardrail_lines)}

## Research implications
1. Add a “parallel width vs iterative depth” decision rule to Hermes/Evy workflow design.
2. Require explicit output paths for generated workflow artifacts; never allow silent global placement for reusable automation.
3. Log per-worker cost, model, input scope, tools, and final merge evidence so wide research jobs remain auditable.
4. Prefer cheaper models for independent scoring/retrieval workers and reserve high-end synthesis for the final merge.

## Follow-up questions
- Should Evy-CLI expose a workflow-runner command for reproducible wide research jobs?
- What should Hermes record for each delegated worker: prompt, model, tools, cost, artifacts, or all of them?
- Which Jason workflows are truly wide enough to justify 20–50 workers?
- Can Keelpin detect unsafe generated workflow scripts before execution?
"""

    if _is_ai_judgment_evidence_talk(transcript, title):
        evidence_lines = _select_lines(transcript, ["evidence problem", "human judgment", "look productive", "old evidence", "quality", "final answer"])
        whiteboard_lines = _select_lines(transcript, ["whiteboard", "live reasoning", "pressure", "push", "update", "confidence"])
        sdrc_lines = _select_lines(transcript, ["situation", "decision", "risk", "change", "rejected", "constraints"])
        artifact_lines = _select_lines(transcript, ["comprehension over generation", "explanation as artifact", "record of real work", "talent board", "portfolio", "resume"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is a judgment evidence brief: as AI makes polished output cheap, the scarce signal becomes visible human judgment — situation framing, decisions, rejected options, risk reasoning, and the change created by the person’s involvement.

## Why this matters for Jason
- This applies directly to AI-assisted engineering: the output artifact is no longer enough; we need provenance of reasoning, review, rejection, risk, and change.
- For Keelpin, “comprehension over generation” maps to AppSec evidence: what risk was seen, what was rejected, what changed, and whether the decision survived scrutiny.
- For Hermes/Evy, briefs and workflows should preserve not only final answers but decision trails: assumptions, alternatives, verification, and unresolved risk.
- For hiring/team evaluation, live whiteboard-style evidence and durable post-hoc artifacts can distinguish judgment from AI polish.

## Key evidence — AI makes old evidence weaker
{bullets(evidence_lines)}

## Key evidence — whiteboard/live reasoning
{bullets(whiteboard_lines)}

## Key evidence — situation / decision / risk / change
{bullets(sdrc_lines)}

## Key evidence — comprehension over generation
{bullets(artifact_lines)}

## Research implications
1. Treat “judgment evidence” as a first-class artifact in agentic work: situation, decision, rejected paths, risk, and change.
2. Extend Keelpin-style provenance beyond code generation into reasoning provenance and risk acceptance records.
3. Have Evy preserve lightweight decision logs for major research/build tasks so future reviews see why a path was chosen.
4. Build evaluation rubrics that score comprehension, risk reasoning, and response to pushback — not just output polish.

## Follow-up questions
- What should Evy capture in a decision log without making the workflow heavy?
- How can Keelpin represent rejected alternatives and accepted risk as graph edges?
- Could generated briefs include a Situation/Decision/Risk/Change section by default for strategic videos?
- What human review signals should be attached to AI-generated code or reports?
"""

    if _is_interpretable_context_methodology_talk(transcript, title):
        structure_lines = _select_lines(transcript, ["folders", "markdown", "plain text", "skills", "scripts", "processes"])
        layer_lines = _select_lines(transcript, ["layer one", "layer two", "level three", "workflow", "context window", "determinism"])
        dialogue_lines = _select_lines(transcript, ["dialogue", "conversation", "chain of decisions", "goals", "constraints", "assumptions"])
        provenance_lines = _select_lines(transcript, ["training data", "markdown files", "methodology", "saved", "track", "engineering context"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is an interpretable context methodology brief: instead of automating the framework layer, the talk argues for engineering plain-text folders, markdown, skills, dialogue, goals, constraints, and decision traces so one agent can navigate reusable context without heavyweight infrastructure.

## Why this matters for Jason
- Hermes/Evy already lives in this pattern: skills, markdown, transcripts, memories, plans, and artifacts become the context substrate the agent can navigate.
- For Keelpin, the crucial signal is not just generated code; it is the dialogue-to-decision chain that produced constraints, assumptions, rejected paths, and methodology.
- This is a strong argument for provenance-first folders: research notes, scripts, audio, briefs, and decisions should be structured so future agents can reuse them with minimal context injection.
- The “don’t automate the wrong layer” warning maps to AppSec too: build the auditable substrate before piling on opaque multi-agent frameworks.

## Key evidence — folders / markdown / skills substrate
{bullets(structure_lines)}

## Key evidence — layer model / context engineering
{bullets(layer_lines)}

## Key evidence — dialogue as decision trace
{bullets(dialogue_lines)}

## Key evidence — reusable methodology / provenance
{bullets(provenance_lines)}

## Research implications
1. Treat context folders and markdown files as first-class software artifacts: versioned, linted, reviewed, and tied to outcomes.
2. Capture dialogue-derived goals, constraints, assumptions, and decisions as provenance edges that Keelpin can reason about.
3. Prefer simple navigable context structures before adding complex agent frameworks or RAG layers.
4. Add lightweight decision extraction to Evy research workflows so a conversation can become durable methodology.

## Follow-up questions
- Should Evy-CLI include a command that extracts goals/constraints/decisions from transcripts into markdown context files?
- How should Keelpin represent dialogue-derived constraints alongside code/property graphs?
- Which Hermes folders should become canonical context libraries for future research runs?
- Can the video-research workflow emit a decision-trace artifact in addition to a brief?
"""

    if _is_ide_native_coding_harness_talk(transcript, title):
        lsp_lines = _select_lines(transcript, ["LSP", "language server", "workspace-level", "structural refactor", "imports", "re-exports"])
        debugger_lines = _select_lines(transcript, ["debugger", "debugpy", "DLV", "breakpoints", "live memory", "stack frames"])
        edit_lines = _select_lines(transcript, ["hash line edits", "content hash", "whitespace", "syntax errors", "token usage"])
        tool_lines = _select_lines(transcript, ["browser tool", "PR review", "sub agents", "PDFs", "hindsight", "memory management"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is an IDE-native coding harness brief: Oh-My-Pi is positioned as an agent harness that treats a project like a live application runtime, using LSP, debugger adapters, hash-anchored edits, browser tooling, PR review, subagents, and memory rather than flat-text guessing.

## Why this matters for Jason
- For Hermes/Evy, this validates adding richer coding-tool context: LSP, DAP/debugpy, browser automation, PR review, and memory as first-class harness capabilities.
- For Keelpin, IDE/runtime-aware edits are AppSec-relevant: structural refactors, import rewrites, live stack state, and exact edit anchors should be traceable.
- Hash line edits are an interesting provenance primitive: smaller edits, fewer token costs, and fewer whitespace/syntax failures, with clearer anchors for review.
- The harness direction is “agent + IDE/runtime substrate,” not merely “LLM reading files.”

## Key evidence — LSP / structural code awareness
{bullets(lsp_lines)}

## Key evidence — debugger/runtime awareness
{bullets(debugger_lines)}

## Key evidence — hash line edits / safe patching
{bullets(edit_lines)}

## Key evidence — browser, review, subagents, memory
{bullets(tool_lines)}

## Research implications
1. Explore LSP/DAP integration for Evy-CLI or Hermes coding workflows so agents can inspect symbols, imports, and live runtime state.
2. Treat content-hash edit anchors as a safer patch model for agent-generated changes and Keelpin provenance.
3. Log debugger sessions and runtime observations as security-relevant evidence, not just development convenience.
4. Compare Oh-My-Pi’s harness features against Hermes/Codex/Claude Code to identify missing tooling lanes.

## Follow-up questions
- Should Hermes expose debugpy/DAP as a first-class tool for coding agents?
- Can Keelpin validate hash-anchored edits against AST/CPG changes?
- What is the minimum trace schema for LSP refactor → patch → test → PR review?
- Which coding jobs need runtime debugger access versus static code inspection only?
"""

    if _is_desktop_personal_agent_talk(transcript, title):
        install_lines = _select_lines(transcript, ["desktop application", "download", "applications folder", "local install", "cloud deploy", "terminal"])
        memory_lines = _select_lines(transcript, ["local memory", "data lives locally", "managed", "backend", "API keys", "custom"])
        action_lines = _select_lines(transcript, ["meeting agent", "control your browser", "control your computer", "runs commands", "writes code", "edits your files"])
        autonomy_lines = _select_lines(transcript, ["crone system", "integrations", "triggers", "gatekeeper", "subconscious loop", "activity log", "approval"])
        return f"""# Research Brief — {title}

Source: {url}
Video ID: {video_id}

## One-line thesis
This is a desktop personal agent brief: OpenHuman packages a consumer-installable desktop AI harness with local memory, hosted/custom backend options, meeting participation, browser/computer control, integrations, triggers, cron-like scheduling, skills, and an auditable subconscious loop.

## Why this matters for Jason
- OpenHuman is a direct comparison point for Hermes/Evy’s product shape: local memory, desktop presence, voice/meeting capability, integrations, background routines, and visible activity logs.
- The local-memory plus managed-backend split is strategically important: it trades privacy/control against ease of use and integration scale.
- For Keelpin, desktop agents create high-risk action surfaces: accessibility/mouse control, microphone, browser control, file edits, commands, OAuth integrations, triggers, and scheduled autonomy.
- For Hermes/Evy, the useful pattern is human-in-the-loop autonomy: read-only background work can run quietly, write/action workflows should request approval and preserve an activity log.

## Key evidence — desktop install / accessibility
{bullets(install_lines)}

## Key evidence — local memory / backend split
{bullets(memory_lines)}

## Key evidence — agent actions / meeting agent
{bullets(action_lines)}

## Key evidence — triggers / subconscious loop / audit
{bullets(autonomy_lines)}

## Research implications
1. Add OpenHuman to the competitive/reference map for Evy: desktop body, local memory, integrations, approvals, and activity log.
2. Model desktop-agent permissions as AppSec artifacts: accessibility, microphone, browser automation, OAuth scopes, commands, file edits, and scheduled jobs.
3. Keep Evy’s background autonomy explicit: wake cadence, skip/act/escalate decisions, approval boundaries, and visible audit trails.
4. Consider “meeting agent” as a future Evy capability, but only with clear disclosure, transcript provenance, and speaking permissions.

## Follow-up questions
- Which OpenHuman patterns should Evy adopt: activity log, trigger gatekeeper, subconscious loop, or meeting agent?
- How should Keelpin score desktop-agent risk across OS permissions, OAuth scopes, and automation commands?
- What Evy actions may run read-only without approval, and what must always escalate to Jason?
- Should Evy’s cron/heartbeat routines expose a user-facing activity log similar to OpenHuman?
"""

    agent_lines = _select_lines(transcript, ["agent", "harness", "tool", "orchestration", "memory", "storage"])
    system_lines = _select_lines(transcript, ["vera", "rubin", "cpu", "bluefield", "ai factory", "liquid", "fabric"])
    pc_lines = _select_lines(transcript, ["spark", "pc", "unified memory", "trillion", "r2-d2", "c3po"])
    physical_lines = _select_lines(transcript, ["cosmos", "physical ai", "robot", "hyperion", "isaac", "humanoid"])

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


def resolve_output_dir(video_id: str, out: str | None = None, out_root: str | None = None) -> Path:
    """Resolve where artifacts for a video should be written."""
    if out:
        return Path(out)
    return Path(out_root or "video-research-output") / video_id


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
    parser.add_argument("url", nargs="+", help="One or more YouTube URLs or video IDs")
    parser.add_argument("--out", default=None, help="Exact output directory for a single URL")
    parser.add_argument("--out-root", default="video-research-output", help="Root output directory for default/batch runs; each video writes under <out-root>/<video_id>")
    parser.add_argument("--language", action="append", default=["en"], help="Caption language preference; repeatable")
    parser.add_argument("--fallback-audio", action="store_true", help="If captions fail, download audio and transcribe with local faster-whisper")
    args = parser.parse_args(argv)

    if args.out and len(args.url) > 1:
        print("--out can only be used with a single URL; use --out-root for batch runs", file=sys.stderr)
        return 2

    failures = 0
    for index, url in enumerate(args.url, start=1):
        video_id = extract_video_id(url)
        out_dir = resolve_output_dir(video_id, out=args.out, out_root=args.out_root)
        try:
            result = fetch_youtube_transcript(url, languages=args.language)
        except Exception as exc:
            if not args.fallback_audio:
                print(f"Caption fetch failed for {url}: {exc}", file=sys.stderr)
                failures += 1
                continue
            try:
                result = transcribe_audio_fallback(url, out_dir)
            except Exception as fallback_exc:
                print(f"Audio fallback failed for {url}: {fallback_exc}", file=sys.stderr)
                failures += 1
                continue
        paths = write_artifacts(result, out_dir, url)
        if len(args.url) > 1:
            print(f"[{index}/{len(args.url)}] video_id: {result.video_id}")
        print(f"title: {result.title}")
        print(f"duration: {result.duration}")
        print(f"source: {result.source}")
        for name, path in paths.items():
            print(f"{name}: {path}")
    return 2 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
