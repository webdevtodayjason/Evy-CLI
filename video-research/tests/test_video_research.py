import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

CLI_PATH = Path(__file__).resolve().parents[1] / "src" / "video_research.py"
spec = importlib.util.spec_from_file_location("video_research", CLI_PATH)
assert spec is not None and spec.loader is not None
video_research = importlib.util.module_from_spec(spec)
sys.modules["video_research"] = video_research
spec.loader.exec_module(video_research)


class VideoResearchTests(unittest.TestCase):
    def test_extract_video_id_from_youtu_be_url_with_si_param(self):
        self.assertEqual(video_research.extract_video_id("https://youtu.be/O8jg-Shxd3o?si=abc"), "O8jg-Shxd3o")

    def test_extract_video_id_from_watch_url(self):
        self.assertEqual(video_research.extract_video_id("https://www.youtube.com/watch?v=O8jg-Shxd3o&list=foo"), "O8jg-Shxd3o")

    def test_format_timestamp(self):
        self.assertEqual(video_research.format_timestamp(716), "11:56")
        self.assertEqual(video_research.format_timestamp(3661), "1:01:01")

    def test_build_brief_includes_source_focus_and_key_sections(self):
        transcript = """
0:14 agentic AI has arrived and useful AI has arrived.
0:51 an agent consists of a large language model sitting inside a harness.
3:48 This is CPU for agents. This CPU is built for agents.
4:16 harness, orchestration, tool use, accessing the database.
7:25 it has 768 GB of memory and could run a trillion parameter model.
9:18 Cosmos watches the physical world and flags what matters.
11:08 We need a reference platform for robotic systems.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/O8jg-Shxd3o",
            title="Jensen highlight reel",
            video_id="O8jg-Shxd3o",
        )
        self.assertIn("# Research Brief", brief)
        self.assertIn("Why this matters for Jason", brief)
        self.assertIn("agent harness", brief.lower())
        self.assertIn("physical ai", brief.lower())
        self.assertIn("Source", brief)

    def test_build_brief_switches_to_agent_auth_when_authmd_detected(self):
        transcript = """
8:07 you need a runtime. It has to be secure, permissions, isolation, and scoped credentials.
9:43 A lot of people describe these things together as the harness.
16:14 that is agentic registration.
17:50 MCP is great but MCP is not enough for this.
18:43 we're calling it auth dot m d.
19:14 Auth.md tells agents how they can become legitimate users in your system.
23:31 converting it into what's called an IDJAG.
30:14 the agent will send that IDJAG assertion and it receives back an access token.
32:32 agent ready is actually the next enterprise ready.
33:55 Our API is the UI.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/Dqp_b8GHLXU",
            title="Unlock Autonomous AI Agents with auth.md",
            video_id="Dqp_b8GHLXU",
        )
        self.assertIn("agent-native registration", brief.lower())
        self.assertIn("IDJAG", brief)
        self.assertIn("MCP is not enough", brief)
        self.assertIn("agent-ready is the next enterprise-ready", brief.lower())
        self.assertIn("Keelpin", brief)

    def test_build_brief_switches_to_agent_lifecycle_when_langsmith_detected(self):
        transcript = """
3:58 they've landed on this new agent development lifecycle.
4:55 first, I want to talk about build, building agents.
12:40 I want to talk about the test phase next.
13:37 So you've built your agent. Now you want to go to production.
18:42 And lastly, we've got monitor.
24:05 agent traces are at the center of the agent development lifecycle.
27:56 today, we're launching SmithDB.
40:59 launch an agent in Langsmith, an ambient proactive action-taking agent called Langsmith Engine.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/jWy39wavbjY",
            title="The Agent Development Lifecycle: Build, Test, Deploy, Monitor",
            video_id="jWy39wavbjY",
        )
        self.assertIn("Agent Development Lifecycle", brief)
        self.assertIn("Build → Test → Deploy → Monitor", brief)
        self.assertIn("SmithDB", brief)
        self.assertIn("traces", brief.lower())
        self.assertIn("Keelpin", brief)

    def test_build_brief_switches_to_future_agent_architecture_when_interrupt_2027_detected(self):
        transcript = """
0:47 what do the agents of the future look like?
1:21 there will be two types of agents.
1:27 long horizon style agents run for minutes and hours and maybe days.
1:34 They do code execution. They do planning. They use subagents.
2:00 a completely different set of agents that latency is a huge factor for.
2:14 Voice becomes a really interesting modality.
3:21 native speech-to-speech native voice models are coming out.
6:42 If you want trust, you need to have some observability into how they're behaving.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/R9K2574YEAg",
            title="The Future of AI Agents: What Will Interrupt 2027 Look Like?",
            video_id="R9K2574YEAg",
        )
        self.assertIn("future agent architecture", brief.lower())
        self.assertIn("long-horizon", brief.lower())
        self.assertIn("latency-sensitive", brief.lower())
        self.assertIn("voice", brief.lower())
        self.assertIn("Keelpin", brief)

    def test_build_brief_switches_to_open_model_evaluation_when_minimax_detected(self):
        transcript = """
0:08 Minimax M3 is a new open source model.
0:42 long horizon agents, large scale coding, and tool use.
1:37 agent performance with strong autonomous task decomposition.
2:26 benchmarks include SWE-Bench and ToolBench.
3:14 nearly 2,000 tool calls.
7:46 Overall, it did a strong job compared with proprietary models.
11:30 MiniMax M3 is one of the best open source AI models.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/p6Npi-HBoRU",
            title="MiniMax M3 IS INSANE! BEST Opensource AI Model! Beats Opus 4.7 and 50x Cheaper!",
            video_id="p6Npi-HBoRU",
        )
        self.assertIn("open model evaluation", brief.lower())
        self.assertIn("long-horizon", brief.lower())
        self.assertIn("coding", brief.lower())
        self.assertIn("tool use", brief.lower())
        self.assertIn("local/private", brief.lower())

    def test_build_brief_switches_to_local_ai_workspace_when_odysseus_detected(self):
        transcript = """
0:12 AI tool called Odyssey S. He calls it an AI workspace.
0:20 something that you should self-host.
0:24 use agents that are based on open code.
0:33 There's also deep research.
0:59 also get memory, email, notes, calendar.
2:25 There are two ways to chat. One is agent and one is chat.
2:30 tools that the AI model can use, which are mainly web search and shell access.
4:20 since it's local, you don't need any internet connection.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/-CoCF9koVfc",
            title="Odysseus + Gemma-4 26B & FREE APIs: RIP Hermes & OpenClaw!",
            video_id="-CoCF9koVfc",
        )
        self.assertIn("local ai workspace", brief.lower())
        self.assertIn("self-hosted", brief.lower())
        self.assertIn("web search", brief.lower())
        self.assertIn("shell access", brief.lower())
        self.assertIn("Hermes/Evy", brief)

    def test_build_brief_switches_to_dynamic_workflows_when_claude_workflows_detected(self):
        transcript = """
0:40 what this feature is and how it works.
1:06 with the release of Claude Opus 4.8, we got dynamic workflows.
2:57 workflows are basically Claude code writing a script that runs these many agents.
3:21 workflows can be saved and re-ran whenever you want.
9:54 depth versus width.
10:37 each agent is a full Claude call.
11:11 bound the scope, name the deliverable.
11:23 slash deep research function automatically invokes a workflow.
13:55 it was storing them somewhere else more global.
15:41 if you want a giant parallel job, use the new dynamic workflows.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/jZgcWCzxh1I",
            title="Claude Code Dynamic Workflows Clearly Explained",
            video_id="jZgcWCzxh1I",
        )
        self.assertIn("dynamic workflows", brief.lower())
        self.assertIn("width", brief.lower())
        self.assertIn("bound the scope", brief.lower())
        self.assertIn("token", brief.lower())
        self.assertIn("Hermes", brief)

    def test_build_brief_switches_to_ai_judgment_evidence_when_resume_whiteboard_detected(self):
        transcript = """
0:00 Microsoft says that 86% of us are treating AI output as just the beginning.
0:28 It's an evidence problem.
1:01 better ways to see human judgment at work.
1:18 the AI age is the age of whiteboards.
4:23 situation, decision, risk, and change.
6:39 judgment under pressure.
7:06 comprehension over generation, explanation as artifact, and a record of real work.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/UsCgEuIAclE",
            title="Microsoft Says 86% Treat AI Output as a Starting Point. Your Resume Just Stopped Working.",
            video_id="UsCgEuIAclE",
        )
        self.assertIn("judgment evidence", brief.lower())
        self.assertIn("comprehension over generation", brief.lower())
        self.assertIn("situation", brief.lower())
        self.assertIn("decision", brief.lower())
        self.assertIn("risk", brief.lower())
        self.assertIn("Keelpin", brief)

    def test_build_brief_switches_to_interpretable_context_methodology_when_folders_markdown_detected(self):
        transcript = """
0:00 Interpretable context methodology.
0:19 they're building folders and markdown files on their computer.
0:44 methodology is about structuring folders, structuring markdown files.
1:01 skills are the right amount of scripts, processes, and ideas.
1:28 instead of creating rag, you give it access to normal databases and folder context structure.
8:55 chain of decisions being made.
12:31 track the decision-making and goal processes where and when it was saved within dialogue.
13:08 engineering context.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/956DPSPX4wg",
            title="You're Automating The Wrong Layer (How 30,000 People Build AI Without Frameworks)",
            video_id="956DPSPX4wg",
        )
        self.assertIn("interpretable context methodology", brief.lower())
        self.assertIn("folders", brief.lower())
        self.assertIn("markdown", brief.lower())
        self.assertIn("dialogue", brief.lower())
        self.assertIn("Keelpin", brief)

    def test_build_brief_switches_to_ide_native_coding_harness_when_oh_my_pi_detected(self):
        transcript = """
0:00 This is Oh My Pi. It's a new AI agent harness built on top of the popular Pi framework.
0:58 native LSP or language server protocol integration.
1:31 full debugger adapter protocol support.
1:45 debugger tools like DLV or debugpy.
1:59 completely model agnostic.
2:26 hash line edits.
2:49 whitespace syntax errors and save up to 61% on LLM token usage.
3:06 its own browser tool.
4:14 PR review tool, sub agents, PDFs, hindsight for agent memory management.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/8ukl-0tlVgM",
            title="Stop Using Claude Code CLI. Use THIS Instead! (Oh-My-Pi)",
            video_id="8ukl-0tlVgM",
        )
        self.assertIn("ide-native coding harness", brief.lower())
        self.assertIn("lsp", brief.lower())
        self.assertIn("debugger", brief.lower())
        self.assertIn("hash line edits", brief.lower())
        self.assertIn("Keelpin", brief)

    def test_build_brief_switches_to_desktop_personal_agent_when_openhuman_detected(self):
        transcript = """
0:00 brand new AI agent called OpenHuman.
0:11 desktop application just like Slack, just like Notion.
0:35 meeting agent can attend a meeting on your behalf and speak in real time.
2:25 personal AI super intelligence with local memory.
3:27 memory of your data lives locally on your machine.
3:52 integrations, 118 plus integrations out of the box.
10:40 control your browser, can control your computer.
10:49 writes code, edits files, runs commands.
11:30 crone system built in.
12:33 subconscious loop wakes itself every 5 minutes.
13:14 activity log to see exactly what the agent did while you were away.
13:51 same skill.md format.
""".strip()
        brief = video_research.build_brief(
            transcript,
            url="https://youtu.be/4xDTGazlYHM",
            title="I am Switching to OpenHuman...",
            video_id="4xDTGazlYHM",
        )
        self.assertIn("desktop personal agent", brief.lower())
        self.assertIn("local memory", brief.lower())
        self.assertIn("subconscious loop", brief.lower())
        self.assertIn("meeting agent", brief.lower())
        self.assertIn("Hermes/Evy", brief)

    def test_classify_video_returns_category_tags_and_relevance_lanes(self):
        transcript = """
0:52 Notebook LM is a free AI tool made by Google.
2:14 connects Notebook LM to your AI agent.
4:22 Hermes stores notes, sources, and research outputs.
5:30 source grounded notebooks help with citations and provenance.
""".strip()
        metadata = video_research.classify_video(
            transcript,
            title="New NotebookLM + Hermes is INSANE! (FREE)",
        )
        self.assertEqual(metadata["category"], "source-grounded research notebook")
        self.assertIn("notebooklm", metadata["tags"])
        self.assertIn("source-grounding", metadata["tags"])
        self.assertIn("hermes-evy", metadata["relevance_lanes"])
        self.assertIn("provenance", metadata["relevance_lanes"])

    def test_write_artifacts_emits_metadata_json_with_category_and_tags(self):
        result = video_research.TranscriptResult(
            video_id="qeM-vMakFQ8",
            title="Understand Any Codebase 10x Faster with Claude, 44k stars on github",
            duration="4:10",
            transcript="0:40 a pipeline of agents crawls the codebase.\n3:05 An architecture agent sorts the layers.",
            source="youtube-captions",
            raw={"segments": []},
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = video_research.write_artifacts(result, Path(tmp), "https://youtu.be/qeM-vMakFQ8")
            self.assertIn("metadata", paths)
            metadata = video_research.json.loads(paths["metadata"].read_text())
            self.assertEqual(metadata["video_id"], "qeM-vMakFQ8")
            self.assertEqual(metadata["category"], "codebase comprehension agent")
            self.assertIn("codebase-analysis", metadata["tags"])
            self.assertIn("keelpin-appsec", metadata["relevance_lanes"])

    def test_update_collection_index_writes_sorted_video_catalogue(self):
        first = {
            "video_id": "b-video-id01",
            "title": "B video",
            "category": "desktop personal agent",
            "tags": ["openhuman"],
            "relevance_lanes": ["hermes-evy"],
            "artifacts": {"brief": "b-video-id01/brief.md"},
        }
        second = {
            "video_id": "a-video-id01",
            "title": "A video",
            "category": "source-grounded research notebook",
            "tags": ["notebooklm"],
            "relevance_lanes": ["provenance"],
            "artifacts": {"brief": "a-video-id01/brief.md"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for item in [first, second]:
                d = root / item["video_id"]
                d.mkdir()
                (d / "metadata.json").write_text(video_research.json.dumps(item), encoding="utf-8")
            index_path = video_research.update_collection_index(root)
            index = video_research.json.loads(index_path.read_text())
            self.assertEqual([v["video_id"] for v in index["videos"]], ["a-video-id01", "b-video-id01"])
            self.assertIn("source-grounded research notebook", index["categories"])
            self.assertIn("notebooklm", index["tags"])

    def test_resolve_output_dir_uses_video_id_under_out_root_for_batch_runs(self):
        out_dir = video_research.resolve_output_dir(
            video_id="R9K2574YEAg",
            out=None,
            out_root="video-research/output",
        )
        self.assertEqual(out_dir, Path("video-research/output") / "R9K2574YEAg")


if __name__ == "__main__":
    unittest.main()
