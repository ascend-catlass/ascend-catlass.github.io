import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import build_index


class BuildIndexTest(unittest.TestCase):
    def test_collect_and_render_verified_wheel(self) -> None:
        digest = "a" * 64
        releases = [
            {
                "draft": False,
                "assets": [
                    {
                        "name": "ascend_catlass_dsl-2.0.1.dev20260909-cp312-cp312-manylinux_2_28_x86_64.whl",
                        "browser_download_url": "https://example.invalid/package.whl",
                        "digest": f"sha256:{digest}",
                    },
                    {
                        "name": "notes.txt",
                        "browser_download_url": "https://example.invalid/notes.txt",
                        "digest": f"sha256:{digest}",
                    },
                ],
            }
        ]

        wheels = build_index.collect_wheels(releases)
        self.assertEqual(len(wheels), 1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_index.write_site(output, wheels)
            page = (output / "simple" / "ascend-catlass-dsl" / "index.html").read_text()
            self.assertIn(f"#sha256={digest}", page)
            self.assertIn(wheels[0].name, page)
            self.assertIn("--pre --extra-index-url", (output / "index.html").read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["files"][0]["sha256"], digest)

    def test_rejects_missing_digest(self) -> None:
        releases = [
            {
                "draft": False,
                "assets": [
                    {
                        "name": "ascend_catlass_dsl-2.0.0-py3-none-any.whl",
                        "browser_download_url": "https://example.invalid/package.whl",
                    }
                ],
            }
        ]
        with self.assertRaisesRegex(RuntimeError, "SHA256"):
            build_index.collect_wheels(releases)

    def test_prefers_newest_release_for_duplicate_filename(self) -> None:
        name = "ascend_catlass_dsl-2.0.1.dev20260912-cp310-cp310-manylinux_2_28_aarch64.whl"
        older = {
            "id": 1,
            "published_at": "2026-09-11T19:24:38Z",
            "draft": False,
            "assets": [
                {
                    "name": name,
                    "browser_download_url": "https://example.invalid/older.whl",
                    "digest": f"sha256:{'a' * 64}",
                }
            ],
        }
        newer = {
            "id": 2,
            "published_at": "2026-09-11T19:54:47Z",
            "draft": False,
            "assets": [
                {
                    "name": name,
                    "browser_download_url": "https://example.invalid/newer.whl",
                    "digest": f"sha256:{'b' * 64}",
                }
            ],
        }

        for releases in ([older, newer], [newer, older]):
            with self.subTest(order=[release["id"] for release in releases]):
                wheels = build_index.collect_wheels(releases)
                self.assertEqual(
                    wheels,
                    [
                        build_index.Wheel(
                            name, "https://example.invalid/newer.whl", "b" * 64
                        )
                    ],
                )

    def test_rejects_ambiguous_duplicate_filename(self) -> None:
        name = "ascend_catlass_dsl-2.0.1.dev20260912-cp310-cp310-manylinux_2_28_aarch64.whl"
        releases = [
            {
                "id": 1,
                "published_at": "2026-09-11T19:54:47Z",
                "draft": False,
                "assets": [
                    {
                        "name": name,
                        "browser_download_url": f"https://example.invalid/{digest}.whl",
                        "digest": f"sha256:{digest * 64}",
                    }
                ],
            }
            for digest in ("a", "b")
        ]

        with self.assertRaisesRegex(RuntimeError, "same publication order"):
            build_index.collect_wheels(releases)


if __name__ == "__main__":
    unittest.main()
