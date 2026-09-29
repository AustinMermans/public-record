"""Bounded, source-reconstructable SEC Item 2.02 exhibit briefs.

Only the newest two 8-K Item 2.02 filings per covered CIK are considered. An
EX-99.1 is selected from the SEC accession header, never guessed from a name.
The displayed headline and excerpt are exact visible exhibit text, not model
summaries or inferred financial results.
"""
from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/business_briefs"
VERSION = "item-202-brief-v1"
MAX_INDEX_BYTES = 1_000_000
MAX_EXHIBIT_BYTES = 2_500_000
MIN_REQUEST_INTERVAL = 0.6  # Below two requests per second, even across companies.
ACCESSION_RE = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
CIK_RE = re.compile(r"\d{10}\Z")
FILENAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
BLOCK_TAGS = {"address", "article", "blockquote", "br", "center", "div", "h1", "h2", "h3", "h4", "li", "p", "section", "table", "td", "th", "tr"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "template", "ix:header"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def source_record(url, payload, suffix, root=ROOT):
    digest = sha256(payload)
    relative = Path("data/business_briefs/raw") / (digest + suffix)
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(payload)
    return {"url": url, "sha256": digest, "raw_path": relative.as_posix()}


def _checked_source(record, root, suffixes):
    if not isinstance(record, dict):
        raise ValueError("Missing source record")
    path = record.get("raw_path", "")
    digest = record.get("sha256", "")
    if not isinstance(path, str) or not re.fullmatch(r"data/business_briefs/raw/[0-9a-f]{64}\.(?:headers|html|txt)", path):
        raise ValueError("Source path outside content-addressed store")
    if Path(path).suffix not in suffixes or Path(path).stem != digest:
        raise ValueError("Source name/hash mismatch")
    payload = (root / path).read_bytes()
    if sha256(payload) != digest:
        raise ValueError("Source bytes/hash mismatch")
    return payload


def accession_base(cik, accession):
    if not CIK_RE.fullmatch(cik) or not ACCESSION_RE.fullmatch(accession):
        raise ValueError("Invalid SEC identity")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"


def index_url(cik, accession):
    return accession_base(cik, accession) + accession + "-index-headers.html"


def target_filings(corporate):
    if not isinstance(corporate, dict) or not isinstance(corporate.get("companies"), list):
        raise ValueError("Missing corporate coverage")
    targets = []
    seen = set()
    for company in corporate["companies"]:
        cik = company["cik"]
        if not CIK_RE.fullmatch(cik):
            raise ValueError("Malformed covered CIK")
        selected = 0
        for filing in company.get("filings", []):
            if filing.get("form") != "8-K" or "2.02" not in filing.get("items", []):
                continue
            accession = filing["id"]
            key = (cik, accession)
            if key in seen:
                raise ValueError("Duplicate accession in corporate coverage")
            seen.add(key)
            base = accession_base(cik, accession)
            if not filing.get("url", "").startswith(base):
                raise ValueError("Corporate filing accession path mismatch")
            targets.append({
                "cik": cik, "company": company["name"], "tickers": company.get("tickers", []),
                "accession": accession, "form": "8-K", "filed": filing["filed"],
                "filing_url": filing["url"], "index_url": index_url(cik, accession),
            })
            selected += 1
            if selected == 2:
                break
    return targets


def validate_index_identity(header_bytes, cik, accession):
    if len(header_bytes) > MAX_INDEX_BYTES:
        raise ValueError("SEC index exceeds byte limit")
    # The SEC -index-headers.html wraps document records in HTML-escaped
    # pseudo-SGML (<DOCUMENT>, <TYPE>, <FILENAME>), while a comment carries
    # the original XML-like header. Decode entities before matching records.
    header = html.unescape(header_bytes.decode("utf-8", errors="strict"))
    lead = header.split("<DOCUMENT>", 1)[0]
    accession_matches = re.findall(r"^\s*ACCESSION NUMBER:\s*(\S+)", lead, re.I | re.M)
    form_matches = re.findall(r"^\s*CONFORMED SUBMISSION TYPE:\s*(\S+)", lead, re.I | re.M)
    filer_match = re.search(r"\bFILER:\s*(.*?)(?=\n\s*(?:SUBJECT COMPANY|FILED BY|REPORTING-OWNER|OWNER DATA):|</SEC-HEADER>|\Z)", lead, re.I | re.S)
    filer_ciks = re.findall(r"^\s*CENTRAL INDEX KEY:\s*(\d{10})", filer_match.group(1), re.I | re.M) if filer_match else []
    if accession_matches != [accession] or form_matches != ["8-K"] or cik not in filer_ciks:
        raise ValueError("SEC index identity/form mismatch")
    return header


def select_exhibit(header_bytes, cik, accession):
    header = validate_index_identity(header_bytes, cik, accession)
    candidates = []
    for block in re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", header, re.I | re.S):
        types = re.findall(r"^\s*<TYPE>\s*([^\r\n<]+)", block, re.I | re.M)
        names = re.findall(r"^\s*<FILENAME>\s*([^\r\n<]+)", block, re.I | re.M)
        if types == ["EX-99.1"]:
            if len(names) != 1:
                raise ValueError("EX-99.1 filename missing or ambiguous")
            candidates.append(names[0].strip())
    if len(candidates) != 1:
        raise ValueError("EX-99.1 missing or ambiguous")
    filename = candidates[0]
    if not FILENAME_RE.fullmatch(filename) or ".." in filename:
        raise ValueError("EX-99.1 unsafe filename")
    if Path(filename).suffix.lower() not in {".htm", ".html", ".txt"}:
        raise ValueError("EX-99.1 unsupported content type")
    return accession_base(cik, accession) + filename


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        style = re.sub(r"\s+", "", attributes.get("style") or "").lower()
        invisible = (tag in SKIP_TAGS or "hidden" in attributes or
                     attributes.get("aria-hidden", "").lower() == "true" or
                     "display:none" in style or "visibility:hidden" in style or
                     bool(self.stack and self.stack[-1][1]))
        if tag not in VOID_TAGS:
            self.stack.append((tag, invisible))
        if tag in BLOCK_TAGS and not invisible:
            self.parts.append("\n" if tag != "td" else " ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in BLOCK_TAGS and not (self.stack and self.stack[-1][1]):
            self.parts.append("\n" if tag != "td" else " ")
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if not (self.stack and self.stack[-1][1]):
            self.parts.append(data)


def visible_lines(payload, url):
    if len(payload) > MAX_EXHIBIT_BYTES:
        raise ValueError("EX-99.1 exceeds byte limit")
    text = payload.decode("utf-8", errors="strict")
    if "\x00" in text:
        raise ValueError("EX-99.1 contains binary data")
    if url.lower().endswith(".txt"):
        raw_lines = text.splitlines()
    else:
        if not re.search(r"<\s*(html|body|div|p|h1|h2|center)\b", text, re.I):
            raise ValueError("EX-99.1 is not parseable HTML")
        parser = VisibleText()
        parser.feed(text)
        parser.close()
        raw_lines = "".join(parser.parts).splitlines()
    return [line for raw in raw_lines if (line := re.sub(r"\s+", " ", html.unescape(raw)).strip())]


def extract_brief(payload, url):
    lines = visible_lines(payload, url)
    if not lines:
        raise ValueError("EX-99.1 has no visible text")
    # Limit interpretation to the opening prose; financial tables and legal
    # boilerplate later in the exhibit are not safe headline sources.
    opening = lines[:35]
    headline_candidates = []
    for index, original in enumerate(opening):
        line = original
        # Some filers split a single headline over two display lines. Joining
        # adjacent visible text with a space is the only allowed normalization.
        if (line.lower().endswith((" reports", " announces")) and index + 1 < len(opening)
                and len(opening[index + 1].split()) <= 7):
            line += " " + opening[index + 1]
        elif (line.endswith(";") and index + 1 < len(opening)
              and len(opening[index + 1].split()) <= 8):
            line += " " + opening[index + 1]
        low = line.lower().strip(" .:-")
        words = line.split()
        if (4 <= len(words) <= 22 and 18 <= len(line) <= 155 and
            not re.fullmatch(r"(?:exhibit|ex)[ .-]*99[ .-]*1|press release|for immediate release|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", low) and
            not low.startswith(("contact", "refer to", "what:", "financial community", "investor relations", "media relations", "forward-looking")) and
            not low.endswith((" and", " or", " of", " for", ";")) and not line.endswith(".") and
            not any(token in low for token in ("supplemental information", "exhibit 99", "8-k exhibit", "news release the ")) and
            not re.match(r"^[•●▪*]", line) and "@" not in line and
            re.search(r"[A-Za-z]{3}", line) and not re.search(r"[.!?].+[.!?]", line)):
            score = (6 if re.search(r"\b(?:reports|announces)\b", low) else 0)
            score += (4 if "results" in low else 0)
            score += (2 if "earnings release" in low else 0)
            score += (1 if "financial" in low else 0)
            score += (3 if "production" in low and "deliver" in low else 0)
            headline_candidates.append((score, -index, line))
    if not headline_candidates:
        raise ValueError("No defensible headline in EX-99.1")
    score, _, headline = max(headline_candidates)
    if score == 0:
        raise ValueError("No release-style headline in EX-99.1")
    candidates = []
    for line in opening:
        if len(line) < 35 or line == headline or len(line) > 1200:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"$])", line):
            words = sentence.split()
            if (6 <= len(words) <= 25 and len(sentence) <= 230 and
                re.search(r"[A-Za-z]{3}", sentence) and
                sentence.count('"') % 2 == 0 and sentence.count('“') == sentence.count('”') and
                not re.search(r"(?:forward-looking statements|safe harbor|investor relations)", sentence, re.I)):
                candidates.append(sentence.strip())
    # Years and generic table introductions are not useful result excerpts.
    # Prefer a source-reported amount/rate/quantity to a prospective target;
    # a mixed-case line beats an all-caps wire header when both qualify.
    candidates = [s for s in candidates if re.search(
        r"\$\s*\(?\d|\b\d[\d,.]*\s*%|\b\d[\d,.]*\s*(?:percent|billion|million|gwh|vehicles|bps|kbd)\b", s, re.I)]
    prose = [s for s in candidates if re.search(
        r"\b(?:was|were|is|are|increased|decreased|grew|rose|fell|up|down|posted|reports?|reported|delivered|generated|produced|deployed|reached|hit|rose|includes?)\b", s, re.I)]
    if prose:
        candidates = prose
    else:
        # Multiple adjacent currency cells without a verb are a table row,
        # not a self-contained reported result.
        candidates = [s for s in candidates if not re.search(r"\$\s*\(?[\d,.]+\s+\$", s)]
    reported = [s for s in candidates if not re.search(r"\b(?:planned|forecast|projected|expected)\b", s, re.I)]
    if reported:
        candidates = reported
    mixed = [s for s in candidates if sum(ch.isupper() for ch in s if ch.isalpha()) <
             .85 * sum(ch.isalpha() for ch in s)]
    if mixed:
        candidates = mixed
    if not candidates:
        raise ValueError("No defensible reported-result excerpt in EX-99.1")
    excerpt = candidates[0]
    return headline, excerpt


class RateLimiter:
    def __init__(self, interval=MIN_REQUEST_INTERVAL):
        self.interval = interval
        self.last = None

    def wait(self):
        if self.last is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        self.last = time.monotonic()


def fetch(url, agent, limit, limiter):
    if not agent or "@" not in agent:
        raise ValueError("SEC_USER_AGENT with identifying contact is required")
    limiter.wait()
    request = Request(url, headers={"User-Agent": agent, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"})
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f"SEC HTTP {response.status}")
            if response.geturl() != url:
                raise ValueError("SEC response redirected outside expected accession URL")
            payload = response.read(limit + 1)
    except HTTPError as error:
        raise ValueError(f"SEC HTTP {error.code}") from None
    except URLError:
        raise ValueError("SEC request failed") from None
    if len(payload) > limit:
        raise ValueError("SEC response exceeds byte limit")
    return payload


def _validate_entry(entry, root):
    cik, accession = entry["cik"], entry["accession"]
    expected_index = index_url(cik, accession)
    if entry["form"] != "8-K" or entry["index_url"] != expected_index:
        raise ValueError("Brief identity/index mismatch")
    status = entry["status"]
    if status not in {"ok", "stale", "metadata_only"}:
        raise ValueError("Unknown brief status")
    index_record = entry.get("index_source")
    source = entry.get("source")
    if status == "metadata_only":
        if entry.get("headline") is not None or entry.get("excerpt") is not None or source is not None:
            raise ValueError("Metadata-only entry contains extracted text")
        if index_record:
            if index_record.get("url") != expected_index:
                raise ValueError("Index URL mismatch")
            validate_index_identity(_checked_source(index_record, root, {".headers"}), cik, accession)
        return
    if not entry.get("captured_at") or not entry.get("attempted_at"):
        raise ValueError("Captured brief missing clocks")
    if status == "stale" and entry["captured_at"] >= entry["attempted_at"]:
        raise ValueError("Stale brief has invalid clocks")
    if not index_record or index_record.get("url") != expected_index:
        raise ValueError("Captured brief missing index source")
    header = _checked_source(index_record, root, {".headers"})
    exhibit_url = select_exhibit(header, cik, accession)
    if not source or source.get("url") != exhibit_url:
        raise ValueError("Exhibit URL does not match index")
    exhibit = _checked_source(source, root, {".html", ".txt"})
    if (".txt" if exhibit_url.lower().endswith(".txt") else ".html") != Path(source["raw_path"]).suffix:
        raise ValueError("Exhibit type mismatch")
    if (entry.get("headline"), entry.get("excerpt")) != extract_brief(exhibit, exhibit_url):
        raise ValueError("Brief text is not reconstructed from source")


def validate_capture(bundle, root=ROOT, corporate=None):
    if bundle.get("schema_version") != 1 or bundle.get("extraction_version") != VERSION:
        raise ValueError("Unsupported brief schema/extraction version")
    briefs = bundle.get("briefs")
    if not isinstance(briefs, list):
        raise ValueError("Missing brief list")
    keys = []
    for entry in briefs:
        _validate_entry(entry, root)
        keys.append((entry["cik"], entry["accession"]))
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate brief accession")
    if corporate is not None:
        expected = target_filings(corporate)
        if keys != [(item["cik"], item["accession"]) for item in expected]:
            raise ValueError("Brief targets do not match current coverage")
        for entry, target in zip(briefs, expected):
            if any(entry.get(k) != target[k] for k in ("company", "tickers", "filed", "filing_url")):
                raise ValueError("Brief metadata does not match SEC submission capture")
    return True


def collect(corporate, previous=None, *, agent=None, root=ROOT, fetcher=fetch, clock=now):
    stamp = clock()
    limiter = RateLimiter()
    previous_by_key = {(b["cik"], b["accession"]): b for b in (previous or {}).get("briefs", [])}
    briefs = []
    for target in target_filings(corporate):
        entry = dict(target, status="metadata_only", headline=None, excerpt=None, source=None,
                     index_source=None, captured_at=None, attempted_at=stamp, error=None)
        old = previous_by_key.get((target["cik"], target["accession"]))
        try:
            header = fetcher(target["index_url"], agent, MAX_INDEX_BYTES, limiter)
            validate_index_identity(header, target["cik"], target["accession"])
            # The retained header also lets us explain missing/ambiguous exhibits.
            entry["index_source"] = source_record(target["index_url"], header, ".headers", root)
            exhibit_url = select_exhibit(header, target["cik"], target["accession"])
            exhibit = fetcher(exhibit_url, agent, MAX_EXHIBIT_BYTES, limiter)
            headline, excerpt = extract_brief(exhibit, exhibit_url)
            suffix = ".txt" if exhibit_url.lower().endswith(".txt") else ".html"
            entry.update(status="ok", headline=headline, excerpt=excerpt,
                         source=source_record(exhibit_url, exhibit, suffix, root),
                         captured_at=stamp)
        except Exception as error:
            # Old text remains visible only when the exact same accession is
            # still selected, its source revalidates, and no new contradictory
            # SEC index has been captured.
            if entry["index_source"] is None and old and old.get("status") in {"ok", "stale"}:
                try:
                    _validate_entry(old, root)
                    entry.update(status="stale", headline=old["headline"], excerpt=old["excerpt"],
                                 source=old["source"], index_source=old["index_source"],
                                 captured_at=old["captured_at"])
                except (ValueError, KeyError, OSError):
                    pass
            entry["error"] = str(error)[:180]
        briefs.append(entry)
    bundle = {"schema_version": 1, "extraction_version": VERSION,
              "attempted_at": stamp, "captured_at": stamp, "briefs": briefs,
              "coverage": "Newest two non-amended Item 2.02 Form 8-K filings per covered CIK in the current SEC submissions snapshot; exact EX-99.1 exhibit only. Not a complete filings feed."}
    validate_capture(bundle, root, corporate)
    return bundle


def main():
    corporate = json.loads((ROOT / "data/corporate/current.json").read_text())
    current = DATA / "current.json"
    previous = json.loads(current.read_text()) if current.exists() else None
    bundle = collect(corporate, previous, agent=os.environ.get("SEC_USER_AGENT"))
    DATA.mkdir(parents=True, exist_ok=True)
    current.write_text(json.dumps(bundle, separators=(",", ":")))
    states = {state: sum(b["status"] == state for b in bundle["briefs"]) for state in ("ok", "stale", "metadata_only")}
    print("SEC Item 2.02 briefs", states)


if __name__ == "__main__":
    main()
