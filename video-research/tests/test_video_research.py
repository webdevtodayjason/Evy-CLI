import importlib.util
import sys
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

    def test_resolve_output_dir_uses_video_id_under_out_root_for_batch_runs(self):
        out_dir = video_research.resolve_output_dir(
            video_id="R9K2574YEAg",
            out=None,
            out_root="video-research/output",
        )
        self.assertEqual(out_dir, Path("video-research/output") / "R9K2574YEAg")


if __name__ == "__main__":
    unittest.main()
