"""Fail-closed SEC exhibit selection, visible text, capture and replay tests."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import business_briefs as briefs

CIK = "0000320193"
ACCESSION = "0000320193-26-000018"
FILING_URL = briefs.accession_base(CIK, ACCESSION) + "aapl-20260730.htm"
EXHIBIT_URL = briefs.accession_base(CIK, ACCESSION) + "earnings.htm"


def header(*, cik=CIK, accession=ACCESSION, form="8-K", documents=None):
    documents = documents if documents is not None else [("8-K", "aapl-20260730.htm"), ("EX-99.1", "earnings.htm")]
    parts = [f"<SEC-DOCUMENT>{accession}-index.html\n<SEC-HEADER>\nACCESSION NUMBER: {accession}\nCONFORMED SUBMISSION TYPE: {form}\nFILER:\n COMPANY DATA:\n CENTRAL INDEX KEY: {cik}\n</SEC-HEADER>\n"]
    parts += [f"<DOCUMENT>\n<TYPE>{kind}\n<FILENAME>{name}\n</DOCUMENT>\n" for kind, name in documents]
    return "".join(parts).encode()


EXHIBIT = b"""<html><head><title>SEC file</title></head><body>
<div>Exhibit 99.1</div><div>Apple reports third quarter results</div>
<div>June quarter records for total company revenue and EPS</div>
<p>CUPERTINO, CALIFORNIA - Apple today announced financial results for its fiscal 2026 third quarter ended June 27, 2026. The Company posted quarterly revenue of $109.4 billion, up 16 percent year over year.</p>
</body></html>"""


def corporate(accession=ACCESSION):
    url = briefs.accession_base(CIK, accession) + "aapl-20260730.htm"
    return {"companies": [{"cik": CIK, "name": "Apple Inc.", "tickers": ["AAPL"], "filings": [
        {"id": accession, "form": "8-K", "items": ["2.02", "9.01"], "filed": "2026-07-30", "url": url},
        {"id": "0000320193-26-000017", "form": "8-K", "items": ["1.01"], "filed": "2026-07-27", "url": briefs.accession_base(CIK, "0000320193-26-000017") + "filing.htm"},
    ]}]}


def fake_fetch(url, agent, limit, limiter):
    if url.endswith("-index-headers.html"):
        return header()
    if url == EXHIBIT_URL:
        return EXHIBIT
    raise AssertionError(url)


class BusinessBriefTests(unittest.TestCase):
    def test_selects_exact_exhibit_under_verified_accession(self):
        self.assertEqual(briefs.select_exhibit(header(), CIK, ACCESSION), EXHIBIT_URL)
        # SEC's real -index-headers.html escapes its document pseudo-SGML.
        escaped = header().decode().replace("<DOCUMENT>", "&lt;DOCUMENT&gt;").replace("</DOCUMENT>", "&lt;/DOCUMENT&gt;").replace("<TYPE>", "&lt;TYPE&gt;").replace("<FILENAME>", "&lt;FILENAME&gt;")
        self.assertEqual(briefs.select_exhibit(escaped.encode(), CIK, ACCESSION), EXHIBIT_URL)
        for kwargs in ({"cik": "0000000001"}, {"accession": "0000320193-26-000019"}, {"form": "10-K"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                briefs.select_exhibit(header(**kwargs), CIK, ACCESSION)

    def test_rejects_ambiguous_missing_unsafe_and_non_html_exhibits(self):
        variants = [
            [("8-K", "main.htm")],
            [("EX-99.1", "one.htm"), ("EX-99.1", "two.htm")],
            [("EX-99.1", "../../other.htm")],
            [("EX-99.1", "image.pdf")],
            [("EX-99.1", "other/earnings.htm")],
        ]
        for documents in variants:
            with self.subTest(documents=documents), self.assertRaises(ValueError):
                briefs.select_exhibit(header(documents=documents), CIK, ACCESSION)

    def test_extracts_literal_visible_text_not_hidden_or_title(self):
        headline, excerpt = briefs.extract_brief(EXHIBIT, EXHIBIT_URL)
        self.assertEqual(headline, "Apple reports third quarter results")
        self.assertEqual(excerpt, "The Company posted quarterly revenue of $109.4 billion, up 16 percent year over year.")
        hidden = b"<html><head><title>Forged headline here</title></head><body><div hidden>Invented earnings headline</div><div style='display:none'>False results were spectacular</div><p aria-hidden='true'>Invented profit up 400 percent.</p><div>Apple reports third quarter results</div><p>Apple posted quarterly revenue of $109.4 billion during the 2026 fiscal third quarter.</p></body></html>"
        h, e = briefs.extract_brief(hidden, EXHIBIT_URL)
        self.assertEqual(h, "Apple reports third quarter results")
        self.assertNotIn("Invented", h + e)

    def test_malformed_source_fails_closed(self):
        for payload in (b"\xff\xfe", b"<script>Apple reports third quarter results", b"<html><body><div hidden>Apple reports third quarter results</div></body></html>"):
            with self.subTest(payload=payload[:20]), self.assertRaises(ValueError):
                briefs.extract_brief(payload, EXHIBIT_URL)

    def test_reported_result_beats_projection_and_wire_header_and_generic_copy_is_rejected(self):
        exxon = b"<html><body><h1>Exxon announces second quarter results</h1><p>Reported EPS of $3.48, or $3.52 adjusted EPS</p><p>Record production is consistent with planned 9% CAGR through 2030, exceeding competitors.</p></body></html>"
        self.assertEqual(briefs.extract_brief(exxon, EXHIBIT_URL)[1], "Reported EPS of $3.48, or $3.52 adjusted EPS")
        jpm = b"<html><body><h1>JPMorgan announces second quarter results</h1><p>JPMORGANCHASE REPORTS NET INCOME OF $21.2 BILLION IN SECOND QUARTER 2026</p><p>Reported revenue of $57.3 billion and managed revenue of $58.0 billion</p></body></html>"
        self.assertEqual(briefs.extract_brief(jpm, EXHIBIT_URL)[1], "Reported revenue of $57.3 billion and managed revenue of $58.0 billion")
        generic = b"<html><body><h1>Berkshire announces first quarter results</h1><p>Operating results for the first quarters of 2026 and 2025 are summarized in the following paragraphs.</p></body></html>"
        with self.assertRaisesRegex(ValueError, "No defensible reported-result excerpt"):
            briefs.extract_brief(generic, EXHIBIT_URL)
        table = b"<html><body><h1>Meta announces second quarter results</h1><p>Three Months Ended June 30, % Change</p><p>Revenue was $60.80 billion, an increase of 28% year-over-year.</p></body></html>"
        self.assertEqual(briefs.extract_brief(table, EXHIBIT_URL)[1], "Revenue was $60.80 billion, an increase of 28% year-over-year.")
        table2 = b"<html><body><h1>Caterpillar announces second quarter results</h1><p>($ in billions except profit per share) 2026 2025</p><p>Second-quarter 2026 sales and revenues increased 24% to $20.5 billion.</p></body></html>"
        self.assertEqual(briefs.extract_brief(table2, EXHIBIT_URL)[1], "Second-quarter 2026 sales and revenues increased 24% to $20.5 billion.")
        percent_only = b"<html><body><h1>Walmart announces second quarter results</h1><p>Revenue growth of 5.9%, up 5.1% in constant currency.</p></body></html>"
        self.assertEqual(briefs.extract_brief(percent_only, EXHIBIT_URL)[1], "Revenue growth of 5.9%, up 5.1% in constant currency.")
        quotation = b'<html><body><h1>Visa announces third quarter results</h1><p>GAAP net income of $5.6 billion, with EPS of $2.97.</p><p>"Visa delivered net revenue up 14% year-over-year. The CEO elaborated later in the quote."</p></body></html>'
        self.assertEqual(briefs.extract_brief(quotation, EXHIBIT_URL)[1], "GAAP net income of $5.6 billion, with EPS of $2.97.")

    def test_capture_replays_exact_bytes_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = briefs.collect(corporate(), agent="Public Record contact@example.com", root=root,
                                     fetcher=fake_fetch, clock=lambda: "2026-09-29T20:00:00+00:00")
            entry = capture["briefs"][0]
            self.assertEqual(entry["status"], "ok")
            self.assertEqual(entry["source"]["url"], EXHIBIT_URL)
            self.assertTrue(briefs.validate_capture(capture, root, corporate()))
            raw = root / entry["source"]["raw_path"]
            original = raw.read_bytes()
            raw.write_bytes(original + b"evil")
            with self.assertRaisesRegex(ValueError, "hash"):
                briefs.validate_capture(capture, root, corporate())
            raw.write_bytes(original)
            entry["source"]["url"] = briefs.accession_base(CIK, "0000320193-26-000019") + "earnings.htm"
            with self.assertRaisesRegex(ValueError, "URL"):
                briefs.validate_capture(capture, root, corporate())

    def test_failed_refresh_retains_only_same_still_covered_accession(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = briefs.collect(corporate(), agent="Public Record contact@example.com", root=root,
                                   fetcher=fake_fetch, clock=lambda: "2026-09-29T20:00:00+00:00")
            def unavailable(*args):
                raise ValueError("SEC HTTP 429")
            stale = briefs.collect(corporate(), first, agent="Public Record contact@example.com", root=root,
                                   fetcher=unavailable, clock=lambda: "2026-09-30T20:00:00+00:00")
            self.assertEqual(stale["briefs"][0]["status"], "stale")
            self.assertEqual(stale["briefs"][0]["captured_at"], first["briefs"][0]["captured_at"])
            self.assertTrue(briefs.validate_capture(stale, root, corporate()))
            changed = corporate("0000320193-26-000019")
            dropped = briefs.collect(changed, first, agent="Public Record contact@example.com", root=root,
                                     fetcher=unavailable, clock=lambda: "2026-09-30T20:00:00+00:00")
            self.assertEqual(dropped["briefs"][0]["status"], "metadata_only")
            self.assertIsNone(dropped["briefs"][0]["excerpt"])
            self.assertTrue(briefs.validate_capture(dropped, root, changed))

    def test_new_ambiguous_index_does_not_keep_stale_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = briefs.collect(corporate(), agent="Public Record contact@example.com", root=root,
                                   fetcher=fake_fetch, clock=lambda: "2026-09-29T20:00:00+00:00")
            def ambiguous(url, *_):
                return header(documents=[("EX-99.1", "one.htm"), ("EX-99.1", "two.htm")])
            changed = briefs.collect(corporate(), first, agent="Public Record contact@example.com", root=root,
                                     fetcher=ambiguous, clock=lambda: "2026-09-30T20:00:00+00:00")
            self.assertEqual(changed["briefs"][0]["status"], "metadata_only")
            self.assertIsNone(changed["briefs"][0]["headline"])
            self.assertTrue(briefs.validate_capture(changed, root, corporate()))

    def test_mismatched_index_is_not_retained_as_a_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def wrong_index(url, *_):
                return header(cik="0000000001")
            capture = briefs.collect(corporate(), agent="Public Record contact@example.com", root=root,
                                     fetcher=wrong_index, clock=lambda: "2026-09-29T20:00:00+00:00")
            entry = capture["briefs"][0]
            self.assertEqual(entry["status"], "metadata_only")
            self.assertIsNone(entry["index_source"])
            self.assertIsNone(entry["headline"])
            self.assertTrue(briefs.validate_capture(capture, root, corporate()))

    def test_only_two_newest_qualifying_filings(self):
        base = corporate()
        filings = base["companies"][0]["filings"]
        for suffix in ("000016", "000015"):
            accession = "0000320193-26-" + suffix
            filings.append({"id": accession, "form": "8-K", "items": ["2.02"],
                            "filed": "2026-06-01", "url": briefs.accession_base(CIK, accession) + "main.htm"})
        targets = briefs.target_filings(base)
        self.assertEqual([t["accession"] for t in targets], [ACCESSION, "0000320193-26-000016"])


if __name__ == "__main__":
    unittest.main()
