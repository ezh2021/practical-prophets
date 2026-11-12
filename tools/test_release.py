"""Offline tests for the public release manifest and derived identifiers."""
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("podcast_release.py")
spec = importlib.util.spec_from_file_location("podcast_release", SOURCE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ManifestTests(unittest.TestCase):
    def test_stable_guids(self):
        es = release.episodes(release.load())
        self.assertEqual([x["episode"] for x in es], [1, 2, 3])
        self.assertEqual(len(set(x["guid"] for x in es)), 3)

    def test_content_addressed_urls(self):
        for e in release.episodes(release.load()):
            url = release.cache_url(e)
            self.assertIn("?rev=v2-", url)
            self.assertIn(e["sha256"][:12], url)
            self.assertTrue(url.startswith(release.BASE_URL))

    def test_public_mp3_matches_manifest(self):
        for e in release.episodes(release.load()):
            self.assertEqual(release.sha256(release.ROOT / e["filename"]), e["sha256"])

    def test_episode_one_revision_history(self):
        ep = release.episodes(release.load())[0]
        previous = ep.get("revision_history", [])
        self.assertGreaterEqual(len(previous), 2)
        self.assertEqual(previous[-1]["status"], "current")
        self.assertEqual(previous[-1]["sha256"], ep["sha256"])


if __name__ == "__main__":
    unittest.main()
