"""SEC Form 4 identities, rows, cached evidence and failure boundaries."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ownership

CIK = "0000102109"
ACCESSION = "0001214659-26-010625"
BASE = ownership.accession_base(CIK, ACCESSION)
FILING_URL = BASE + "xslF345X06/marketforms-73810.xml"
RAW_URL = BASE + "marketforms-73810.xml"
XML = b"""<?xml version="1.0"?>
<ownershipDocument><documentType>4</documentType><periodOfReport>2026-08-17</periodOfReport>
<issuer><issuerCik>102109</issuerCik><issuerName>Example Energy</issuerName></issuer>
<reportingOwner><reportingOwnerId><rptOwnerCik>12345</rptOwnerCik><rptOwnerName>Ada Buyer</rptOwnerName></reportingOwnerId><reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>0</isOfficer></reportingOwnerRelationship></reportingOwner>
<reportingOwner><reportingOwnerId><rptOwnerCik>67890</rptOwnerCik><rptOwnerName>Second Owner</rptOwnerName></reportingOwnerId><reportingOwnerRelationship><isDirector>false</isDirector><isOfficer>true</isOfficer><officerTitle>CFO</officerTitle></reportingOwnerRelationship></reportingOwner>
<aff10b5One>1</aff10b5One>
<nonDerivativeTable>
<nonDerivativeTransaction><securityTitle><value>Common Stock</value></securityTitle><transactionDate><value>2026-08-17</value></transactionDate><transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>1200</value></transactionShares><transactionPricePerShare><value>4.1208</value><footnoteId id="F1" /></transactionPricePerShare><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts><postTransactionAmounts><sharesOwnedFollowingTransaction><value>21200</value></sharesOwnedFollowingTransaction></postTransactionAmounts><ownershipNature><directOrIndirectOwnership><value>I</value></directOrIndirectOwnership><natureOfOwnership><value>By fund</value></natureOfOwnership></ownershipNature></nonDerivativeTransaction>
<nonDerivativeTransaction><securityTitle><value>Common Stock</value></securityTitle><transactionDate><value>2026-08-17</value></transactionDate><transactionCoding><transactionCode>F</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>100</value></transactionShares><transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable><derivativeTable><derivativeTransaction><securityTitle><value>Option</value></securityTitle><transactionDate><value>2026-08-17</value></transactionDate><transactionCoding><transactionCode>M</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>20</value></transactionShares><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts><underlyingSecurity><underlyingSecurityTitle><value>Common Stock</value></underlyingSecurityTitle><underlyingSecurityShares><value>20</value></underlyingSecurityShares></underlyingSecurity></derivativeTransaction></derivativeTable>
<footnotes><footnote id="F1">Weighted average price; see original filing.</footnote></footnotes></ownershipDocument>"""


def corporate(url=FILING_URL, form="4"):
    return {"companies": [{"cik": CIK, "name": "Example Energy", "tickers": ["EXE"], "filings": [
        {"id": ACCESSION, "form": form, "filed": "2026-08-18", "accepted_at": "2026-08-18T13:00:00Z", "url": url}
    ]}]}


class OwnershipTests(unittest.TestCase):
    def test_xml_url_strips_only_display_transform(self):
        self.assertEqual(ownership.raw_url(CIK, ACCESSION, FILING_URL), RAW_URL)
        self.assertEqual(ownership.raw_url(CIK, ACCESSION, RAW_URL), RAW_URL)
        for bad in [BASE + "../bad.xml", BASE + "other/file.xml", BASE + "form4.htm",
                    ownership.accession_base("0000102110", ACCESSION) + "form4.xml"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ownership.raw_url(CIK, ACCESSION, bad)

    def test_rows_keep_filing_level_owners_and_footnotes_without_multiplying(self):
        doc = ownership.parse_xml(XML, CIK, ACCESSION, "4")
        self.assertEqual(len(doc["owners"]), 2)
        self.assertTrue(doc["owners"][1]["officer"])
        self.assertFalse(doc["owners"][1]["director"])
        self.assertEqual(len(doc["rows"]), 3)
        purchase, withheld, exercise = doc["rows"]
        self.assertEqual(purchase["id"], f"{CIK}:{ACCESSION}:non_derivative:1")
        self.assertEqual((purchase["code"], purchase["direction"], purchase["ownership"]), ("P", "A", "I"))
        self.assertEqual(purchase["footnotes"], [{"id": "F1", "text": "Weighted average price; see original filing."}])
        self.assertEqual((withheld["code"], withheld["direction"]), ("F", "D"))
        self.assertEqual((exercise["table"], exercise["code"], exercise["underlying_security"]),
                         ("derivative", "M", "Common Stock"))
        self.assertTrue(doc["filing_plan_indicated"])

    def test_wrong_issuer_document_type_and_entity_declarations_fail_closed(self):
        variants = [(XML.replace(b"<issuerCik>102109", b"<issuerCik>102110"), "issuer"),
                    (XML.replace(b"<documentType>4", b"<documentType>4/A"), "type"),
                    (b"<!DOCTYPE ownershipDocument>" + XML, "entities"),
                    (XML.replace(b'<footnote id="F1">', b'<footnote id="F2">'), "footnote")]
        for payload, label in variants:
            with self.subTest(label=label), self.assertRaises(ValueError):
                ownership.parse_xml(payload, CIK, ACCESSION, "4")

    def test_collect_replays_raw_and_reuses_only_same_verified_accession(self):
        calls = []
        def fetcher(url, agent, limit, limiter):
            calls.append(url)
            return XML
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = ownership.collect(corporate(), agent="Public Record contact@example.com", root=root,
                                      fetcher=fetcher, clock=lambda: "2026-09-29T20:00:00+00:00")
            self.assertEqual(calls, [RAW_URL])
            self.assertTrue(ownership.validate_capture(first, root, corporate()))
            again = ownership.collect(corporate(), first, agent="Public Record contact@example.com", root=root,
                                      fetcher=lambda *_: self.fail("Cached source refetched"),
                                      clock=lambda: "2026-09-30T20:00:00+00:00")
            self.assertTrue(again["forms"][0]["cached"])
            self.assertEqual(again["forms"][0]["captured_at"], first["forms"][0]["captured_at"])
            raw = root / first["forms"][0]["source"]["raw_path"]
            original = raw.read_bytes()
            raw.write_bytes(original + b"tampered")
            with self.assertRaisesRegex(ValueError, "hash"):
                ownership.validate_capture(first, root, corporate())

    def test_failed_new_capture_does_not_invent_transaction_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = ownership.collect(corporate(), agent="Public Record contact@example.com",
                                       root=Path(tmp), fetcher=lambda *_: (_ for _ in ()).throw(ValueError("SEC HTTP 403")))
            entry = bundle["forms"][0]
            self.assertEqual(entry["status"], "metadata_only")
            self.assertIsNone(entry["document"])
            self.assertIsNone(entry["source"])
            self.assertTrue(ownership.validate_capture(bundle, Path(tmp), corporate()))

    def test_different_issuer_is_proven_and_excluded_not_counted_as_failure(self):
        payload = XML.replace(b"<issuerCik>102109", b"<issuerCik>920760").replace(
            b"<issuerName>Example Energy", b"<issuerName>Lennar Corp")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = ownership.collect(corporate(), root=root, fetcher=lambda *_: payload)
            entry = bundle["forms"][0]
            self.assertEqual(entry["status"], "other_issuer")
            self.assertEqual(entry["reported_issuer_cik"], "0000920760")
            self.assertIsNone(entry["document"])
            self.assertTrue(ownership.validate_capture(bundle, root, corporate()))

    def test_parser_upgrade_replays_verified_old_bytes_without_sec_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = ownership.collect(corporate(), root=root, fetcher=lambda *_: XML)
            first["forms"][0]["document"]["owners"][1]["officer"] = False
            upgraded = ownership.collect(corporate(), first, root=root,
                                         fetcher=lambda *_: self.fail("Verified raw source refetched"))
            self.assertTrue(upgraded["forms"][0]["document"]["owners"][1]["officer"])
            self.assertTrue(ownership.validate_capture(upgraded, root, corporate()))


if __name__ == "__main__":
    unittest.main()
