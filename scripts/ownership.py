"""Source-replayed SEC Form 4 transaction rows for the selected CIK universe.

The filing is the unit of disclosure. A row may have multiple reporting owners;
neither a row nor a code is an investment signal or proof of trading venue.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from business_briefs import RateLimiter, accession_base, fetch
from collection_errors import safe_sec_error

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/ownership"
EXTRACTION_VERSION = "sec-form4-rows-v2"
MAX_XML_BYTES = 1_000_000
CIK_RE = re.compile(r"[0-9]{10}\Z")
ACCESSION_RE = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
XML_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.xml\Z", re.I)
SOURCE_PATH_RE = re.compile(r"data/ownership/raw/([0-9a-f]{64})\.xml\Z")


class OtherIssuer(ValueError):
    def __init__(self, cik, name):
        super().__init__("Form 4 concerns a different issuer")
        self.cik = cik
        self.name = name


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text(node, path):
    child = node.find(path) if node is not None else None
    return child.text.strip() if child is not None and child.text and child.text.strip() else None


def value(node, path):
    return text(node, path + "/value")


def flag(node, path):
    raw = text(node, path)
    if raw in {None, "0", "false"}:
        return False
    if raw in {"1", "true"}:
        return True
    raise ValueError("Form 4 ownership relationship flag is malformed")


def raw_url(cik, accession, filing_url):
    base = accession_base(cik, accession)
    if not isinstance(filing_url, str) or not filing_url.startswith(base):
        raise ValueError("Form 4 URL is outside the issuer/accession directory")
    parsed = urlsplit(filing_url)
    if parsed.query or parsed.fragment or parsed.netloc != "www.sec.gov":
        raise ValueError("Form 4 URL has an unsupported host or suffix")
    tail = filing_url[len(base):].split("/")
    if len(tail) == 2 and re.fullmatch(r"xslF[0-9A-Za-z]+", tail[0]):
        tail = tail[1:]
    if len(tail) != 1 or not XML_NAME_RE.fullmatch(tail[0]) or ".." in tail[0]:
        raise ValueError("Form 4 primary document is not a safe XML filename")
    return base + tail[0]


def target_filings(corporate):
    if not isinstance(corporate, dict) or not isinstance(corporate.get("companies"), list):
        raise ValueError("Missing SEC company coverage")
    targets, seen = [], set()
    for company in corporate["companies"]:
        cik = company["cik"]
        if not CIK_RE.fullmatch(cik):
            raise ValueError("Malformed covered CIK")
        for filing in company.get("filings", []):
            if filing.get("form") not in {"4", "4/A"}:
                continue
            accession = filing["id"]
            if not ACCESSION_RE.fullmatch(accession) or (cik, accession) in seen:
                raise ValueError("Duplicate or malformed Form 4 accession")
            seen.add((cik, accession))
            targets.append({
                "cik": cik, "company": company["name"], "tickers": company.get("tickers", []),
                "accession": accession, "form": filing["form"], "filed": filing["filed"],
                "accepted_at": filing.get("accepted_at"), "filing_url": filing["url"],
                "xml_url": raw_url(cik, accession, filing["url"]),
            })
    return targets


def parse_xml(payload, cik, accession, form):
    if len(payload) > MAX_XML_BYTES or b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("Form 4 XML exceeds limit or declares external entities")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise ValueError("Form 4 XML is malformed") from error
    if root.tag != "ownershipDocument" or text(root, "documentType") != form:
        raise ValueError("Ownership document type mismatch")
    issuer = root.find("issuer")
    issuer_cik = text(issuer, "issuerCik")
    if not issuer_cik or not issuer_cik.isdigit():
        raise ValueError("Form 4 issuer CIK missing or malformed")
    if issuer_cik.zfill(10) != cik:
        raise OtherIssuer(issuer_cik.zfill(10), text(issuer, "issuerName"))
    owners = []
    for owner in root.findall("reportingOwner"):
        owner_id = owner.find("reportingOwnerId")
        owner_cik = text(owner_id, "rptOwnerCik")
        name = text(owner_id, "rptOwnerName")
        if not owner_cik or not owner_cik.isdigit() or not name:
            raise ValueError("Form 4 reporting-owner identity missing")
        relationship = owner.find("reportingOwnerRelationship")
        owners.append({
            "cik": owner_cik.zfill(10), "name": name,
            "director": flag(relationship, "isDirector"),
            "officer": flag(relationship, "isOfficer"),
            "ten_percent_owner": flag(relationship, "isTenPercentOwner"),
            "other": flag(relationship, "isOther"),
            "officer_title": text(relationship, "officerTitle"),
            "other_text": text(relationship, "otherText"),
        })
    if not owners:
        raise ValueError("Form 4 has no reporting owner")
    notes = {}
    for footnote in root.findall("footnotes/footnote"):
        note_id = footnote.get("id")
        if not note_id or note_id in notes:
            raise ValueError("Form 4 footnote identity is missing or duplicated")
        notes[note_id] = " ".join(" ".join(footnote.itertext()).split())
    rows = []
    for table, path in (("non_derivative", "nonDerivativeTable/nonDerivativeTransaction"),
                        ("derivative", "derivativeTable/derivativeTransaction")):
        for ordinal, row in enumerate(root.findall(path), start=1):
            references = list(dict.fromkeys(ref.get("id") for ref in row.iter("footnoteId")))
            if any(ref not in notes for ref in references):
                raise ValueError("Form 4 row references an absent footnote")
            transaction_date = value(row, "transactionDate")
            if transaction_date:
                datetime.fromisoformat(transaction_date)
            code = text(row, "transactionCoding/transactionCode")
            direction = value(row, "transactionAmounts/transactionAcquiredDisposedCode")
            if code and not re.fullmatch(r"[A-Z]", code):
                raise ValueError("Form 4 transaction code is malformed")
            if direction and direction not in {"A", "D"}:
                raise ValueError("Form 4 acquisition/disposition code is malformed")
            rows.append({
                "id": f"{cik}:{accession}:{table}:{ordinal}", "table": table, "ordinal": ordinal,
                "transaction_date": transaction_date, "security": value(row, "securityTitle"),
                "code": code, "direction": direction,
                "shares": value(row, "transactionAmounts/transactionShares"),
                "price_per_share": value(row, "transactionAmounts/transactionPricePerShare"),
                "owned_after": value(row, "postTransactionAmounts/sharesOwnedFollowingTransaction"),
                "ownership": value(row, "ownershipNature/directOrIndirectOwnership"),
                "ownership_nature": value(row, "ownershipNature/natureOfOwnership"),
                "underlying_security": value(row, "underlyingSecurity/underlyingSecurityTitle"),
                "underlying_shares": value(row, "underlyingSecurity/underlyingSecurityShares"),
                "footnotes": [{"id": ref, "text": notes[ref]} for ref in references],
            })
    plan = text(root, "aff10b5One")
    if plan not in {None, "0", "1", "false", "true"}:
        raise ValueError("Unrecognized filing-level plan indicator")
    period = text(root, "periodOfReport")
    if period:
        datetime.fromisoformat(period)
    return {
        "issuer_name": text(issuer, "issuerName"), "owners": owners, "rows": rows,
        "period_of_report": period, "filing_plan_indicated": plan in {"1", "true"} if plan is not None else None,
    }


def source_record(url, payload, root=ROOT):
    digest = hashlib.sha256(payload).hexdigest()
    relative = f"data/ownership/raw/{digest}.xml"
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(payload)
    return {"url": url, "sha256": digest, "raw_path": relative}


def read_source(source, expected, root=ROOT):
    match = SOURCE_PATH_RE.fullmatch(source.get("raw_path", "")) if isinstance(source, dict) else None
    if not match or source.get("url") != expected or source.get("sha256") != match[1]:
        raise ValueError("Form 4 raw source path or URL mismatch")
    payload = (root / source["raw_path"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != source["sha256"]:
        raise ValueError("Form 4 raw source hash mismatch")
    return payload


def validate_entry(entry, root=ROOT):
    expected = raw_url(entry["cik"], entry["accession"], entry["filing_url"])
    if entry["xml_url"] != expected or entry["form"] not in {"4", "4/A"}:
        raise ValueError("Form 4 entry identity mismatch")
    if entry["status"] == "metadata_only":
        if entry.get("source") is not None or entry.get("document") is not None or entry.get("captured_at") is not None:
            raise ValueError("Metadata-only Form 4 has extracted rows")
        return
    if entry["status"] not in {"ok", "other_issuer"} or not entry.get("source") or not entry.get("captured_at"):
        raise ValueError("Unknown or incomplete Form 4 status")
    payload = read_source(entry["source"], expected, root)
    if entry["status"] == "other_issuer":
        if entry.get("document") is not None:
            raise ValueError("Other-issuer Form 4 exposes transaction rows")
        try:
            parse_xml(payload, entry["cik"], entry["accession"], entry["form"])
        except OtherIssuer as mismatch:
            if entry.get("reported_issuer_cik") != mismatch.cik or entry.get("reported_issuer_name") != mismatch.name:
                raise ValueError("Other-issuer identity does not replay from raw source") from None
        else:
            raise ValueError("Other-issuer exclusion no longer matches XML")
    elif entry["document"] != parse_xml(payload, entry["cik"], entry["accession"], entry["form"]):
        raise ValueError("Form 4 rows do not replay from raw source")


def validate_capture(bundle, root=ROOT, corporate=None):
    if bundle.get("schema_version") != 1 or bundle.get("extraction_version") != EXTRACTION_VERSION:
        raise ValueError("Unsupported Form 4 capture version")
    forms = bundle.get("forms")
    if not isinstance(forms, list):
        raise ValueError("Missing Form 4 entries")
    keys = []
    for entry in forms:
        validate_entry(entry, root)
        keys.append((entry["cik"], entry["accession"]))
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate Form 4 accession")
    if corporate is not None:
        targets = target_filings(corporate)
        if len(targets) != len(forms):
            raise ValueError("Form 4 capture does not cover selected filings")
        for entry, target in zip(forms, targets):
            if any(entry.get(key) != expected for key, expected in target.items()):
                raise ValueError("Form 4 entry differs from SEC submission target")
    return True


def collect(corporate, previous=None, *, agent=None, root=ROOT, fetcher=fetch, clock=now):
    stamp = clock()
    limiter = RateLimiter()
    prior = {(item["cik"], item["accession"]): item for item in (previous or {}).get("forms", [])}
    forms = []
    for target in target_filings(corporate):
        entry = dict(target, status="metadata_only", document=None, source=None,
                     captured_at=None, attempted_at=stamp, cached=False, error=None,
                     reported_issuer_cik=None, reported_issuer_name=None)
        old = prior.get((target["cik"], target["accession"]))
        if old and old.get("status") in {"ok", "other_issuer"} and old.get("xml_url") == target["xml_url"]:
            try:
                validate_entry(old, root)
                entry.update(status=old["status"], document=old["document"], source=old["source"],
                             captured_at=old["captured_at"], cached=True,
                             reported_issuer_cik=old.get("reported_issuer_cik"),
                             reported_issuer_name=old.get("reported_issuer_name"))
            except (ValueError, KeyError, OSError):
                # Parser upgrades can replay verified immutable bytes without
                # issuing hundreds of redundant SEC requests.
                try:
                    payload = read_source(old.get("source"), target["xml_url"], root)
                    document = parse_xml(payload, target["cik"], target["accession"], target["form"])
                    entry.update(status="ok", document=document, source=old["source"],
                                 captured_at=old["captured_at"], cached=True)
                except OtherIssuer as mismatch:
                    entry.update(status="other_issuer", document=None, source=old["source"],
                                 captured_at=old["captured_at"], cached=True,
                                 reported_issuer_cik=mismatch.cik, reported_issuer_name=mismatch.name)
                except (ValueError, KeyError, OSError):
                    pass
        if entry["status"] == "metadata_only":
            try:
                payload = fetcher(target["xml_url"], agent, MAX_XML_BYTES, limiter)
                document = parse_xml(payload, target["cik"], target["accession"], target["form"])
                entry.update(status="ok", document=document,
                             source=source_record(target["xml_url"], payload, root), captured_at=stamp)
            except OtherIssuer as mismatch:
                entry.update(status="other_issuer", source=source_record(target["xml_url"], payload, root),
                             captured_at=stamp, reported_issuer_cik=mismatch.cik,
                             reported_issuer_name=mismatch.name)
            except Exception as error:
                entry["error"] = safe_sec_error(error)
        forms.append(entry)
    bundle = {
        "schema_version": 1, "extraction_version": EXTRACTION_VERSION,
        "attempted_at": stamp, "forms": forms,
        "coverage": "All selected Forms 4 and 4/A within the current 12-ownership-form-per-CIK submissions quota. "
                    "Transactions are filing rows, not market-wide trades; amended filings remain separate.",
    }
    validate_capture(bundle, root, corporate)
    return bundle


def main():
    corporate = json.loads((ROOT / "data/corporate/current.json").read_text())
    current = DATA / "current.json"
    previous = json.loads(current.read_text()) if current.exists() else None
    bundle = collect(corporate, previous, agent=os.environ.get("SEC_USER_AGENT"))
    DATA.mkdir(parents=True, exist_ok=True)
    current.write_text(json.dumps(bundle, separators=(",", ":")))
    counts = {state: sum(item["status"] == state for item in bundle["forms"])
              for state in ("ok", "other_issuer", "metadata_only")}
    print("SEC Form 4 transaction rows", counts)


if __name__ == "__main__":
    main()
