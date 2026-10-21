import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prefixmaps.ingest.ingest_jsonld import (
    from_prefixcc,
    is_excluded_from_prefixcc,
    load_prefixcc_exclusions,
)
from tests import INPUT_DIR

EXPECTED = [
    ("owl", "http://www.w3.org/2002/07/owl#"),
    ("foaf", "http://xmlns.com/foaf/0.1/"),
]


class TextETLForPrefixCC(unittest.TestCase):
    def test_prefix_cc(self):
        ctxt = from_prefixcc()
        for pe in ctxt.prefix_expansions:
            print(pe)
        pm = ctxt.as_dict()
        pmi = ctxt.as_inverted_dict()
        for pfx, ns in EXPECTED:
            self.assertEqual(pm[pfx], ns)
            self.assertEqual(pmi[ns], pfx)

    def test_prefix_cc_exclusions(self):
        """Test that excluded entries are dropped when ingesting prefix.cc."""
        with open(INPUT_DIR / "prefix-cc.context.jsonld", encoding="utf-8") as file:
            response = mock.Mock(json=mock.Mock(return_value=json.load(file)))
        with mock.patch("requests.get", return_value=response):
            pm = from_prefixcc().as_dict()
        for pfx, ns in EXPECTED:
            self.assertEqual(pm[pfx], ns)
        # the input has veelana and ljkl on excluded hosts, and the excluded prefixes leaks and bgcat
        for pfx in ["veelana", "ljkl", "leaks", "bgcat"]:
            self.assertNotIn(pfx, pm)

    def test_excluded_hosts(self):
        """Test that hosts are excluded with their subdomains, but not lookalike domains."""
        exclusions = {"hosts": {"onlyfans.com": "spam"}, "prefixes": {}}
        for namespace, expected in [
            ("https://onlyfans.com/x/", True),
            ("http://www.onlyfans.com/x/", True),
            ("https://OnlyFans.com/x/", True),
            ("https://notonlyfans.com/x/", False),
            ("https://example.org/onlyfans.com/", False),
            ("https://onlyfans.com./x/", True),
            ("http://[abc/", False),
        ]:
            with self.subTest(namespace=namespace):
                self.assertEqual(expected, is_excluded_from_prefixcc("x", namespace, exclusions))

    def test_prefix_cc_without_context(self):
        """Test that a prefix.cc response without a JSON-LD context is still rejected."""
        response = mock.Mock(json=mock.Mock(return_value={}))
        with mock.patch("requests.get", return_value=response):
            with self.assertRaises(ValueError):
                from_prefixcc()

    def test_exclusions_loader(self):
        """Test that empty sections are allowed, but misspelled sections are rejected."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefixcc.excluded.yaml"
            for text, expected in [
                ("", {"hosts": {}, "prefixes": {}}),
                ("hosts:\nprefixes:\n  a: spam\n", {"hosts": {}, "prefixes": {"a": "spam"}}),
            ]:
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    self.assertEqual(expected, load_prefixcc_exclusions(path))
            path.write_text("prefixess:\n  a: spam\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_prefixcc_exclusions(path)

    def test_exclusions_file(self):
        """Test that the exclusions file has reasons for all entries."""
        exclusions = load_prefixcc_exclusions()
        for kind, entries in exclusions.items():
            for entry, reason in entries.items():
                with self.subTest(kind=kind, entry=entry):
                    self.assertTrue(reason)
