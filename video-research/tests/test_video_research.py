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


if __name__ == "__main__":
    unittest.main()
