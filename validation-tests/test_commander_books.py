"""Atlas Commander book MCP tools: bounded reads, paths, and provider handling."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = (Path(__file__).resolve().parents[1] / "atlas-rust-desktop" / "src-tauri" / "resources" / "atlas" / "src")
SPEC = importlib.util.spec_from_file_location("book_commander", SOURCE / "book_commander.py")
books = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(books)


class CommanderBooks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.item = {"id": 11, "title": "Example Book", "authors": [{"name": "A Writer"}],
                     "languages": ["en"], "subjects": ["Fiction"], "copyright": False,
                     "formats": {"text/plain; charset=utf-8": "https://www.gutenberg.org/cache/epub/11/pg11.txt",
                                 "application/epub+zip": "https://www.gutenberg.org/cache/epub/11/pg11.epub"}}

    def tearDown(self):
        self.temp.cleanup()

    def test_exposes_five_separate_tools(self):
        tools = books.tool_definitions(lambda p, r=None: {"inputSchema": {"properties": p}}, offline=False)
        self.assertEqual([tool["name"] for tool in tools], ["book_search", "book_list", "book_view", "book_read", "book_download"])
        self.assertEqual(books.tool_definitions(lambda *_: {}, offline=True), [])

    def test_search_filters_non_public_entries_and_caps_results(self):
        with patch.object(books, "_api", return_value={"count": 2, "results": [self.item, {**self.item, "id": 12, "copyright": True}]}):
            found = books.call_tool("book_search", {"query": "example", "limit": 1}, self.root)
        self.assertEqual([b["id"] for b in found["books"]], [11])

    def test_read_has_bounded_text_and_public_domain_check(self):
        with patch.object(books, "_fetch_book", return_value=[self.item]), patch.object(books, "_request", return_value=(b"hello world", "text/plain")):
            out = books.call_tool("book_read", {"book_id": "11", "max_chars": 5}, self.root)
        self.assertEqual(out["text"], "hello")
        self.assertTrue(out["truncated"])
        with patch.object(books, "_fetch_book", return_value=[{**self.item, "copyright": True}]):
            with self.assertRaisesRegex(ValueError, "not marked public-domain"):
                books.call_tool("book_read", {"book_id": "11"}, self.root)

    def test_download_is_confined_and_never_overwrites(self):
        with patch.object(books, "_fetch_book", return_value=[self.item]), patch.object(books, "_request", return_value=(b"book", "application/epub+zip")):
            result = books.call_tool("book_download", {"book_id": "11", "format": "EPUB"}, self.root)
            self.assertTrue((self.root / result["path"]).is_file())
            with self.assertRaisesRegex(ValueError, "already exists"):
                books.call_tool("book_download", {"book_id": "11", "format": "EPUB"}, self.root)

    def test_rejects_bad_ids_and_untrusted_urls(self):
        with self.assertRaisesRegex(ValueError, "book_id"):
            books.call_tool("book_view", {"book_id": "../../secret"}, self.root)
        with self.assertRaisesRegex(ValueError, "Only HTTPS"):
            books._request("https://example.org/secret", "text/plain")

    def test_list_rejects_bad_page(self):
        with self.assertRaisesRegex(ValueError, "page must be"):
            books.call_tool("book_list", {"page": None}, self.root)

    def test_offline_mode_blocks_network_tools(self):
        with patch.dict(os.environ, {"ATLAS_COMMANDER_OFFLINE": "1"}):
            with self.assertRaisesRegex(ValueError, "switched off"):
                books.call_tool("book_search", {"query": "x"}, self.root)


if __name__ == "__main__":
    unittest.main()
