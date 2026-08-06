import os
import tempfile
import unittest

from pdf_operations import (
    flatten_pages,
    parse_page_expression,
    parse_page_order,
    safe_filename,
    split_by_count,
    trim_pages,
    unique_filename,
)


class PageOperationTests(unittest.TestCase):
    def test_parse_expression_expands_ranges_and_deduplicates(self):
        self.assertEqual(parse_page_expression("2, 5-7, 6", 10), [1, 4, 5, 6])

    def test_parse_expression_rejects_invalid_pages(self):
        with self.assertRaises(ValueError):
            parse_page_expression("1, nope", 5)
        with self.assertRaises(ValueError):
            parse_page_expression("0-2", 5)

    def test_parse_order_keeps_written_order(self):
        self.assertEqual(parse_page_order("3, 1-2, 4", 4), [2, 0, 1, 3])

    def test_parse_order_rejects_repeated_pages(self):
        with self.assertRaises(ValueError):
            parse_page_order("3, 1-3", 5)
        with self.assertRaises(ValueError):
            parse_page_order("2, 2", 5)

    def test_parse_order_rejects_invalid_pages(self):
        with self.assertRaises(ValueError):
            parse_page_order("1, nope", 5)
        with self.assertRaises(ValueError):
            parse_page_order("", 5)
        with self.assertRaises(ValueError):
            parse_page_order("6", 5)

    def test_trim_pages(self):
        self.assertEqual(trim_pages(6, 1, 2), [1, 2, 3])
        with self.assertRaises(ValueError):
            trim_pages(3, 2, 1)

    def test_split_by_count(self):
        self.assertEqual(split_by_count(7, 3), [[0, 1, 2], [3, 4, 5], [6]])

    def test_filename_is_safe_and_pdf(self):
        self.assertEqual(safe_filename("bad:name?.txt"), "bad-name-.txt.pdf")
        self.assertEqual(safe_filename("..."), "output.pdf")

    def test_unique_filename_considers_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            open(os.path.join(directory, "part.pdf"), "w").close()
            used = set()
            self.assertEqual(unique_filename("part.pdf", directory, used), "part-2.pdf")
            self.assertEqual(unique_filename("part.pdf", directory, used), "part-3.pdf")

    def test_flatten_pages_preserves_order(self):
        self.assertEqual(flatten_pages([[2, 0], [3]]), [2, 0, 3])


if __name__ == "__main__":
    unittest.main()
