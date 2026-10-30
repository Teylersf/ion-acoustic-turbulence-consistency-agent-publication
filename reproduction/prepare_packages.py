"""Offline agent-edition adapter. No network, Git, credentials or submission.

Requires byte-pinned bundled inputs and an explicit private outgoing directory.
Only agent front matter, figure routes, platform grouping and reversible prose
citation formatting change; scientific text is never shortened or padded.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REPOSITORY = "https://github.com/Teylersf/ion-acoustic-turbulence-consistency-audit"
AGENT_REPOSITORY = "https://github.com/Teylersf/ion-acoustic-turbulence-consistency-agent-publication"
AGENT_NAME = "Lattice Audit Agent"
AGENT_ID = "agent_29b9bf7a"
IDENTITY = "gist:7c74312cf47dcc31c789a8b1c3dedd25"
HEADINGS = ["Introduction", "Related Work", "Methodology", "Results", "Discussion", "Limitations", "Conclusion"]
TAGS = ["ion-acoustic-turbulence", "time-dependent-growth", "Vlasov-Poisson", "plasma-dielectric", "source-energy-budget", "reproducibility"]
MATH = re.compile(r"\\\[.*?\\\]|\\\(.*?\\\)|\$\$.*?\$\$|(?<![\\$])\$(?!\$).*?(?<!\\)\$(?!\$)", re.S)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
SCRIPT_BYTES = Path(__file__).read_bytes()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")

def words(text):
    return len(re.findall(r"\b[\w'-]+\b", text))

def section_map(text):
    matches = list(re.finditer(r"^## (.+)$", text, re.M))
    result = {}
    for i, match in enumerate(matches):
        if match[1] in result:
            raise ValueError("Duplicate canonical top-level section")
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result[match[1]] = text[match.end():end].strip()
    return result

def scientific_sections(parsed):
    numbered = [(h, b) for h, b in parsed.items() if re.fullmatch(r"[1-6]\. .+", h)]
    if [int(h.split(".", 1)[0]) for h, _ in numbered] != list(range(1, 7)):
        raise ValueError("Expected exactly canonical scientific sections 1 through 6")
    if list(parsed) != ["Abstract", *(h for h, _ in numbered), "References"]:
        raise ValueError("Unrecognized, reordered or omitted top-level section; no appendix is expected")
    return numbered

def protected(text):
    return {
        "math": MATH.findall(text),
        "tables": re.findall(r"(?m)^(?:[ \t]*\|[^\n]*\|[ \t]*(?:\n|$))+", text),
        "quotations": re.findall(r"(?m)^(?:>[^\n]*(?:\n|$))+", text),
        "code_fences": re.findall(r"(?ms)^```[^\n]*\n.*?^```[ \t]*$", text),
        "proof_markers": re.findall(r"(?m)^(?:#{3,6}\s+)?(?:\*\*)?Proof\b[^\n]*", text),
        "figures": IMAGE.findall(text),
    }

def paragraphs(text):
    return Counter(block.strip() for block in re.split(r"\n\s*\n", text.strip())
                   if block.strip() and not re.fullmatch(r"#{1,6} .+", block.strip()))

def reference_records(text):
    """Five genuine canonical references, including two URL-only code sources."""
    date_raw = (ROOT / "reproduction/reference-date-provenance.json").read_bytes()
    if sha(date_raw) != "61b254be4b8a1fb888a3ea3f3acdd8d2ffcd65a74ae3f6e610c6acc78ce8aca1":
        raise ValueError("Reference-date provenance changed")
    date = json.loads(date_raw)
    if date["reference4"]["year"] != 2022 or date["reference4"]["commit"] != "69f26286dcc7640024804ba6b1c5ea16d409f759":
        raise ValueError("Historical source timestamp basis changed")
    matches = list(re.finditer(r"^\[(\d+)\] (.+?)(?=\n\n\[\d+\] |\Z)", text, re.M | re.S))
    identities = [
        ("A two-dimensional numerical study of ion-acoustic turbulence", ["Z. Liu", "R. White", "M. Francisquez", "L. M. Milanese", "N. F. Loureiro"], 2024, "https://doi.org/10.1017/S0022377824000060", "10.1017/S0022377824000060"),
        ("A two-dimensional numerical study of ion-acoustic turbulence—ERRATUM", ["Z. Liu", "R. White", "M. Francisquez", "L. M. Milanese", "N. F. Loureiro"], 2024, "https://doi.org/10.1017/S0022377824000291", "10.1017/S0022377824000291"),
        ("Input files for the 2023 ion-acoustic turbulence study", ["Z. Liu and collaborators", "Gkeyll Team"], 2023, "https://github.com/gkeyllorg/gkyl-paper-inp/tree/7209ddbfe432b1826df3aa1f7f9fa7f32053a3af/2023_JPP_iat", None),
        ("Historical Gkeyll solver source", ["Gkeyll Team"], 2022, "https://github.com/liangwang0734/gkyl/commit/69f26286dcc7640024804ba6b1c5ea16d409f759", None),
        ("Computational evidence for Growth-law and model consistency in driven ion-acoustic turbulence", ["T. Kalin"], 2026, "https://doi.org/10.5281/zenodo.23786452", "10.5281/zenodo.23786452"),
    ]
    if len(matches) != 5:
        raise ValueError("Review the complete source11 bibliography")
    refs, originals = [], []
    for i, (match, identity) in enumerate(zip(matches, identities), 1):
        title, authors, year, url, doi = identity
        record = match[2].strip()
        if int(match[1]) != i or title not in record or url not in record or any(a not in record.split(title, 1)[0] for a in authors):
            raise ValueError("Reference identity changed")
        if i != 4 and str(year) not in record:
            raise ValueError("Canonical reference year changed")
        originals.append(match[0].strip())
        normalized = {"ref_id": str(i), "type": "external", "title": title, "authors": authors, "year": year, "url": url, "source": "doi" if doi else "url"}
        if doi:
            normalized["doi"] = doi
        refs.append(normalized)
    if "\n\n".join(originals) != text:
        raise ValueError("A complete canonical bibliography record was omitted")
    return refs, originals

def author_year_citations(text, references):
    """Reformat prose markers reversibly; mathematics and code stay exact."""
    labels = {"1": "Liu et al., 2024a", "2": "Liu et al., 2024b", "3": "Liu and Gkeyll Team, 2023", "4": "Gkeyll Team, 2022", "5": "Kalin, 2026"}
    if {r["ref_id"] for r in references} != set(labels):
        raise ValueError("Review author-year map against the complete bibliography")
    protected_spans = [(m.start(), m.end()) for m in MATH.finditer(text)]
    for pattern in [r"(?ms)^```[^\n]*\n.*?^```[ \t]*$", r"`[^`\n]+`"]:
        protected_spans.extend((m.start(), m.end()) for m in re.finditer(pattern, text))
    pattern = re.compile(r"\[([0-9]+(?:\s*,\s*[0-9]+)*)(,\s*[A-Za-z][^\]]*)?\](?!\()")
    parts, ledger, cursor, length = [], [], 0, 0
    for match in pattern.finditer(text):
        if any(match.start() < end and match.end() > start for start, end in protected_spans):
            continue
        ids = [x.strip() for x in match[1].split(",")]
        if any(x not in labels for x in ids):
            raise ValueError("Unresolved prose reference marker")
        prefix = text[cursor:match.start()]
        parts.append(prefix); length += len(prefix)
        rewritten = "[" + "; ".join(labels[x] for x in ids) + (match[2] or "") + "]"
        ledger.append({"canonical": match[0], "adapted": rewritten,
                       "reference_ids": ids, "adapted_start": length,
                       "adapted_end": length + len(rewritten)})
        parts.append(rewritten); length += len(rewritten); cursor = match.end()
    parts.append(text[cursor:])
    converted = "".join(parts)
    if restore_citations(converted, ledger) != text:
        raise ValueError("Author-year transformation is not exactly reversible")
    return converted, ledger

def restore_citations(text, ledger):
    for row in reversed(ledger):
        start, end = row["adapted_start"], row["adapted_end"]
        if text[start:end] != row["adapted"]:
            raise ValueError("Citation reversal locator or text changed")
        text = text[:start] + row["canonical"] + text[end:]
    return text


def safe(name, data):
    """Do not leak local paths, credentials or operational state into outputs."""
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe package route")
    if not name.lower().endswith((".png", ".pdf")):
        text = data.decode("utf-8")
        # This generic reproduction runtime is intentionally public in H.
        scrubbed = text.replace("C:/Python 313/python.exe", "PYTHON")
        scrubbed = scrubbed.replace("C:\\Python 313\\python.exe", "PYTHON")
        if name == "reproduction/canonical/.gitignore":
            scrubbed = scrubbed.replace(".publishing-access/", "PRIVATE_IGNORE_PATTERN/")
        if name == "reproduction/canonical/data/computational-artifact-manifest.json":
            scrubbed = scrubbed.replace('".publishing-access/**"', '"PRIVATE_EXCLUSION_PATTERN/**"')
        if re.search(r"(?i)(?:(?<![A-Z0-9])[A-Z]:[\\/]|/mnt/[a-z]/|/home/|/root/|\.publishing-access)", scrubbed):
            raise ValueError("Private location in public file: " + name)
        if re.search(r"(?i)(?:Bearer\s+[A-Za-z0-9._-]{12,}|(?:session_token|access_token|api_key)\s*[=:]\s*[\"']?[A-Za-z0-9._-]{12,}|gh[pousr]_[A-Za-z0-9]{20,})", text):
            raise ValueError("Credential-shaped value in public file: " + name)


def inputs(args):
    raw = (ROOT / "reproduction/pinned-inputs.json").read_bytes()
    if sha(raw) != args.expected_input_inventory_sha256:
        raise ValueError("Mixed-pin input inventory changed")
    inventory = json.loads(raw)
    for key, value in {
        "computational_commit": args.expected_code_commit,
        "computational_tree": args.expected_code_tree,
        "canonical_content_commit": args.canonical_content_commit,
        "computational_file_count": 50, "paper_support_file_count": 16,
        "file_count": 66,
    }.items():
        if inventory.get(key) != value:
            raise ValueError("Input inventory mismatch: " + key)
    rows = inventory["files"]
    if len(rows) != 66 or len({r["package_path"] for r in rows}) != 66:
        raise ValueError("Missing or duplicate copied files")
    copies = {}
    roles = Counter()
    for row in rows:
        route = row["package_path"]
        if route != "reproduction/canonical/" + row["source_path"]:
            raise ValueError("Unexpected copy route")
        data = (ROOT / route).read_bytes()
        if len(data) != row["bytes"] or sha(data) != row["sha256"]:
            raise ValueError("Pinned bytes differ: " + route)
        role = row["role"]
        expected = args.expected_code_commit if role == "immutable_computational_snapshot" else args.canonical_content_commit
        if row["source_revision"] != expected:
            raise ValueError("Wrong source revision")
        safe(route, data)
        copies[route] = data
        roles[role] += 1
    if roles != Counter({"immutable_computational_snapshot": 50, "canonical_paper_and_review_support": 16}):
        raise ValueError("Wrong source scopes")
    comp = {r["source_path"]: r for r in rows if r["role"] == "immutable_computational_snapshot"}
    manifest = json.loads(copies["reproduction/canonical/data/computational-artifact-manifest.json"])
    records = manifest["files"]
    if set(comp) != {r["path"] for r in records} | {"data/computational-artifact-manifest.json"}:
        raise ValueError("Incomplete frozen computational manifest")
    for row in records:
        if comp[row["path"]]["sha256"] != row["sha256"]:
            raise ValueError("Frozen manifest byte mismatch")
    return copies, inventory, raw


def arrangement(numbered):
    first = numbered[0][1].split("\n\n")
    ending = numbered[5][1].split("\n\n")
    if len(first) != 3 or len(ending) != 6:
        raise ValueError("Review source11 paragraph boundaries")
    if not ending[1].startswith("A non-Maxwellian central second moment") or not ending[2].startswith("The original producer checks") or not ending[3].startswith("The supported result is"):
        raise ValueError("Limitations/conclusion mapping changed")
    added = ["### " + numbered[i][0] for i in (1, 2, 3, 5)]
    bodies = [first[0], "\n\n".join(first[1:]),
              added[0] + "\n\n" + numbered[1][1],
              added[1] + "\n\n" + numbered[2][1] + "\n\n" + added[2] + "\n\n" + numbered[3][1],
              numbered[4][1] + "\n\n" + added[3] + "\n\n" + ending[0],
              "\n\n".join(ending[1:3]), "\n\n".join(ending[3:])]
    if any(not body for body in bodies):
        raise ValueError("Empty platform group")
    return bodies, added


def main():
    if sys.flags.optimize:
        raise RuntimeError("Ordinary Python required; -O disables preservation assertions")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outgoing-dir", type=Path, required=True)
    for name in ("expected-code-commit", "expected-code-tree", "canonical-content-commit",
                 "expected-manuscript-sha256", "expected-pdf-sha256", "expected-input-inventory-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    outgoing = args.outgoing_dir.resolve()
    canonical = ROOT.parent / "ion-acoustic-turbulence-consistency-audit"
    if outgoing.is_relative_to(ROOT) or outgoing.is_relative_to(canonical):
        raise ValueError("Outgoing API bodies must stay outside both repositories")
    for value in (args.expected_code_commit, args.expected_code_tree, args.canonical_content_commit):
        if not re.fullmatch(r"[a-f0-9]{40}", value):
            raise ValueError("Full source commit/tree pins required")
    for value in (args.expected_manuscript_sha256, args.expected_pdf_sha256, args.expected_input_inventory_sha256):
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Full SHA256 required")
    if args.expected_code_commit == args.expected_code_tree:
        raise ValueError("Commit and tree are distinct objects")
    source, inventory, inventory_raw = inputs(args)
    md = source["reproduction/canonical/paper/manuscript.md"]
    pdf = source["reproduction/canonical/paper/main.pdf"]
    if sha(md) != args.expected_manuscript_sha256 or sha(pdf) != args.expected_pdf_sha256:
        raise ValueError("Paper content pins changed")
    text = md.decode("utf-8")
    if "\r" in text:
        raise ValueError("Canonical LF must stay exact")
    parsed = section_map(text)
    numbered = scientific_sections(parsed)
    science = "\n\n".join(body for _, body in numbered)
    title = re.search(r"^# (.+)$", text, re.M)[1]
    version, date = re.search(r"^Version ([^;\s]+); (.+)$", text, re.M).groups()
    meta_raw = source["reproduction/canonical/submissions/metadata.json"]
    meta = json.loads(meta_raw)
    for key, expected in {"title": title, "abstract": parsed["Abstract"], "author": "Taylor Kalin",
                          "version": "1.0.0", "scientific_code_commit": args.expected_code_commit,
                          "repository": CANONICAL_REPOSITORY, "agentpub_paper_type": "short_communication"}.items():
        if meta.get(key) != expected:
            raise ValueError("Canonical metadata changed: " + key)
    assert "**Taylor Kalin**" in text.split("## Abstract", 1)[0]
    assert args.expected_code_commit in science and "https://doi.org/" + meta["code_doi"] in science
    references, original_refs = reference_records(parsed["References"])
    assert len(references) == 5
    image_routes = {}
    for _, link in IMAGE.findall(science):
        if not re.fullmatch(r"\.\./figures/[a-z-]+\.png", link):
            raise ValueError("Unrecognized figure route")
        filename = link.rsplit("/", 1)[1]
        local = "reproduction/canonical/figures/" + filename
        if local not in source:
            raise ValueError("Figure not pinned")
        remote = "https://raw.githubusercontent.com/Teylersf/ion-acoustic-turbulence-consistency-audit/" + args.expected_code_commit + "/figures/" + filename
        image_routes[link] = (local, remote)
    assert len(image_routes) == 2

    def adapt(body, remote=False):
        for old, pair in image_routes.items():
            body = body.replace("](" + old + ")", "](" + pair[int(remote)] + ")")
        return body

    def restore(body, remote=False):
        for old, pair in image_routes.items():
            body = body.replace("](" + pair[int(remote)] + ")", "](" + old + ")")
        return body

    front = ("# " + title + "\n\n**" + AGENT_NAME + "**\n\n"
             "Authorized agent-only edition. Human operator and canonical author: **Taylor Kalin**.\n\n"
             "AgentPub identity: `" + AGENT_ID + "`; AAES identity: `" + IDENTITY + "`.\n\n"
             "Canonical author: https://taylorkalin.com ; ORCID 0009-0003-9000-9315.\n\n"
             "Version " + version + "; " + date + "\n\n"
             "**Agent-edition disclosure.** All scientific paragraphs, mathematics, equations, derivations, figures, captions, references and original disclosures are retained. "
             "This front byline/disclosure and figure routes are adapted. AgentPub alone additionally groups paragraphs into venue sections and uses reversible documented author-year prose citations. "
             "The canonical author remains Taylor Kalin. Internal AI-assisted checks are not independent human peer review.\n\n")
    paper = front + "## Abstract\n\n" + parsed["Abstract"] + "\n\n" + "\n\n".join(
        "## " + h + "\n\n" + adapt(body) for h, body in numbered) + "\n\n## References\n\n" + parsed["References"] + "\n"
    grouped, added = arrangement(numbered)
    sections, ledgers = [], {}
    for heading, body in zip(HEADINGS, grouped):
        content, ledger = author_year_citations(adapt(body, True), references)
        ledgers[heading] = ledger
        sections.append({"heading": heading, "content": content,
                         "citations": sorted({r for row in ledger for r in row["reference_ids"]}, key=int)})
    restored = "\n\n".join(restore(restore_citations(s["content"], ledgers[s["heading"]]), True) for s in sections)
    for heading in added:
        if restored.count(heading + "\n\n") != 1:
            raise ValueError("Added source heading changed")
        restored = restored.replace(heading + "\n\n", "", 1)
    local = section_map(paper)
    restored_local = "\n\n".join(restore(b) for _, b in scientific_sections(local))
    assert restored == restored_local == science
    assert paragraphs(restored) == paragraphs(science)
    assert protected(restored) == protected(restored_local) == protected(science)
    assert local["Abstract"] == parsed["Abstract"] and local["References"] == parsed["References"]
    tags = re.findall(r"\\tag\{([^{}]+)\}", science)
    assert tags == list(map(str, range(1, 11)))
    schema_raw = (ROOT / "reproduction/agentpub-paper-schema.json").read_bytes()
    limits = json.loads(schema_raw)["paper_types"]["short_communication"]["constraints"]
    caps = {s["heading"]: {"unicode_codepoints": len(s["content"]),
                           "UTF16_code_units": len(s["content"].encode("utf-16-le")) // 2} for s in sections}
    body_words = sum(words(s["content"]) for s in sections)
    guideline_checks = {
        "title": len(title) <= limits["title"]["max_chars"],
        "abstract": words(parsed["Abstract"]) <= limits["abstract"]["max_words"],
        "references": len(references) >= limits["references"]["min_count"],
        "body_words": limits["body_word_count"]["min_words"] <= body_words <= limits["body_word_count"]["max_words"],
        "required_sections": set(limits["sections"]["required"]) <= set(HEADINGS),
        "section_order": [h for h in limits["sections"]["must_appear_in_this_order"] if h in HEADINGS] == HEADINGS,
        "section_character_caps": all(max(c.values()) <= 49000 for c in caps.values()),
        "tags": limits["tags"]["min_count"] <= len(TAGS) <= limits["tags"]["max_count"] and all(len(t) <= limits["tags"]["max_chars_each"] for t in TAGS),
    }
    if not all(guideline_checks.values()):
        raise ValueError("Selected live paper-type constraints failed: " + str(guideline_checks))
    note = ("Authorized agent-only edition by Lattice Audit Agent; human operator and canonical author Taylor Kalin, ORCID 0009-0003-9000-9315. "
            "Canonical: " + CANONICAL_REPOSITORY + "/blob/" + args.canonical_content_commit + "/paper/manuscript.md . "
            "Six complete canonical bodies map to seven venue groups at plain-paragraph boundaries, in original scientific order; four source subheadings are added and exactly removable. "
            "All scientific paragraphs, ordered mathematics, ten equations, original figures/full captions, bibliography and disclosures are retained after reversing only declared image routes and prose citation substitutions. "
            "The local paper keeps numeric markers; AgentPub uses reversible [Author, Year] labels. The same-author 2024 article and erratum are labeled 2024a (ID1) and 2024b (ID2). "
            "ID3 is the legitimate 2023 input-deposit URL. ID4 is the legitimate historical solver URL, with 2022 metadata taken from the cached primary commit timestamp, not an invented publication year or DOI. The date basis is recorded in reference-date-provenance.json. "
            "No scientific shortening, padding or new reference is introduced. Exact model/token usage was not recorded; agent_model='not recorded' and total_tokens=-1 are missing-data markers, not estimates. "
            "Claims distinguish literal printed formulas and conditional continuum identities from unknown simulation/postprocessing behavior. The existing acknowledgement-only erratum, valid variance-one plasma-dispersion convention, source benchmarks, tabulated normalizations and empirical duration controls are retained. "
            "The released Main input and declared historical revision are configuration evidence, not a recovered executed binary. The initial .02 omega_pe source-work identity is a periodic continuum witness, not measured run power or an explanation of source curves. "
            "Two complete inline Markdown figure/caption pairs link to immutable H. No undocumented structured-image keys or HTML are guessed. Complete typeset canonical PDF: " + CANONICAL_REPOSITORY + "/releases/download/v1.0.0/main.pdf . "
            "Computational H is " + args.expected_code_commit + "; paper/build/metadata/review support is separately pinned at " + args.canonical_content_commit + ". Original code is MIT; original text/figures CC BY 4.0; upstream input copies retain their own MIT notice. No historical solver code or source publication PDF is redistributed. "
            "Both formal agent gates remain closed; this study has no verified final Publish.fun disposition. A quota or validation failure, software DOI or another paper's outcome is not acceptance, rejection, eligibility or release. Offline preparation is not submission or publication. Internal AI-assisted checks are not external human peer review. "
            "Normalized fields retain five genuine identities, with complete canonical records verbatim below:\n\n" + parsed["References"])
    payload = {"title": title, "abstract": parsed["Abstract"], "paper_type": "short_communication",
               "authors": [{"agent_id": AGENT_ID, "display_name": AGENT_NAME, "model_type": "not recorded"}],
               "sections": sections, "references": references, "tags": TAGS,
               "metadata": {"agent_model": "not recorded", "agent_platform": "Codex desktop", "total_tokens": -1, "submission_note": note}}
    now = datetime.now(timezone.utc).isoformat()
    context = {"prepared_at_utc": now, "publication_state": "local_prepared_not_submitted", "canonical_version": version,
               "computational_commit": args.expected_code_commit, "computational_tree": args.expected_code_tree,
               "canonical_content_commit": args.canonical_content_commit, "canonical_manuscript_sha256": sha(md),
               "AgentPub_submission_gate_open": False, "AAES_submission_gate_open": False,
               "own_Publishfun_final_disposition_verified": False, "formal_submission_performed": False,
               "public_agent_repository_verified": False,
               "note": "Conservative offline state. Root owns the first Publish.fun submission and live disposition. A preflight never opens a formal gate. No acceptance, closure, release or agent eligibility is inferred."}
    metadata = {"aaes_version": "4.2", "title": title, "abstract": parsed["Abstract"], "canonical_version": version,
                "author_ids": [IDENTITY], "submitted_at": now, "timestamp_scope": "local preparation, not registration",
                "tags": TAGS, "agentpub_paper_type": "short_communication",
                "computational_commit": args.expected_code_commit, "computational_tree": args.expected_code_tree,
                "canonical_content_commit": args.canonical_content_commit,
                "generation_environment": {"model": "not recorded", "tools": ["Python", "exact rational arithmetic", "mpmath", "NumPy", "Matplotlib"],
                    "prompt_strategy": "Complete article/erratum reading and edition comparison, exact and high-precision formula controls, source/deck semantics, retained positive/benign interpretations and internal mathematical/citation/visual review.",
                    "notes": "Lattice Audit Agent; human operator and canonical author Taylor Kalin. Self-funded. No estimated model/token usage, target-run recovery or independent human peer review."},
                "novelty_statement": "Bounded technical clarification of printed time-dependent growth, literal threshold arithmetic, forcing/dielectric/beta displays and disclosed model terms. Exact thermal-convention rescue, positive controls and implementation uncertainty are preserved; no new nonlinear theory, measured source power or invalid source simulation is claimed."}
    claims = [
        {"text": "The displayed time-dependent energy law doubles the integrated exponent under the article's instantaneous-rate approximation.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 2, Eqs. (1)-(2); exact integration, logarithmic derivative and anchor controls.", "confidence_note": "Printed formula only; the actual source Figure 1 postprocessing is unavailable and no curve failure is inferred."},
        {"text": "The retained E11 reduction agrees with repaired integration, while the quoted E12 does not solve its literal equality at the stated seed.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 3, Eqs. (3)-(4); independent Lambert-W and monotone roots, explicit width-convention sensitivity.", "confidence_note": "A trapping-width multiplier 1.86116 reconciles the reported field; this is not a universal revised threshold or rejection of the observed run regimes."},
        {"text": "The printed species-force, dielectric-reduction and beta factors have bounded internal inconsistencies.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 4, Eqs. (5)-(8); current slope, imaginary-factor cancellation and Gaussian normalization controls.", "confidence_note": "Actual released species force is correct. A valid variance-one Z convention rescues the apparent thermal sqrt(2) discrepancy; no bad implemented roots or heating diagnostic is claimed."},
        {"text": "The released Main/declaration includes self-collisions and a fixed source; zero mean source moments do not force zero continuum electrostatic work.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 5, Eqs. (9)-(10); declared source/Poisson semantics, exact positive-density Fourier work witnesses.", "confidence_note": "Initial periodic self-adjoint Poisson identity only. No measured injected power, nonlinear impact or executed-binary identity is established."},
        {"text": "The source's tabulated normalization, saturation and empirical duration arithmetic remain supported, and all fifty computational files are preserved.", "kind": "finding", "status": "proposed", "evidence_summary": "Section 6; eleven ENL/five Wsat entries, duration 2025 and software DOI 10.5281/zenodo.23786452.", "confidence_note": "Positive arithmetic and reproducibility controls are not independent validation of empirical fits, source simulations or external human peer review."},
    ]
    registration = {"source": "github:Teylersf/ion-acoustic-turbulence-consistency-agent-publication",
                    "submission": {"kind": "paper", "maturity": "final"},
                    "project": {"title": title, "summary": parsed["Abstract"], "status": "active",
                                "research_question": "Are the source growth/normalization displays and literal threshold calculation consistent, and what additional terms are specified by the released model?"},
                    "claims": claims}
    blocks = protected(science)
    checks = {"prepared_at_utc": now, "canonical_version": version,
              "preparer_sha256": sha(SCRIPT_BYTES), "pinned_input_inventory_sha256": sha(inventory_raw),
              "canonical_manuscript_sha256": sha(md), "canonical_PDF_sha256": sha(pdf), "canonical_metadata_sha256": sha(meta_raw),
              "computational_commit": args.expected_code_commit, "computational_tree": args.expected_code_tree,
              "canonical_content_commit": args.canonical_content_commit, "code_doi": meta["code_doi"],
              "copied_pinned_files": inventory["files"], "copy_counts": {"computational_H": 50, "paper_build_metadata_and_review_release": 16, "total": 66},
              "canonical_scientific_sections": 6, "platform_sections": HEADINGS,
              "mapping": "Original scientific order: Introduction: section 1 paragraph 1; Related Work: section 1 paragraphs 2-3; Methodology: section 2; Results: sections 3-4; Discussion: section 5 plus section 6 paragraph 1; Limitations: section 6 paragraphs 2-3; Conclusion: section 6 paragraphs 4-6. Full paragraph bodies are preserved.",
              "added_platform_headings": added,
              "full_scientific_text_exact_after_declared_reversal": True, "ordered_paragraphs_and_protected_blocks_preserved": True,
              "abstract_and_full_bibliography_exact": True, "canonical_bibliography_verbatim_in_payload_metadata": True,
              "math_segments": len(blocks["math"]), "protected_block_counts": {k: len(v) for k, v in blocks.items()},
              "numbered_equation_tags": tags, "figures": len(image_routes), "references": len(references),
              "scientific_section_bodies": [{"heading": h, "sha256": sha(b.encode())} for h, b in numbered],
              "citation_format": {"documented_style": "[Author, Year]", "instructions_URL": "https://api.agentpub.org/v1/instructions",
                  "reversal_ledger_by_section": ledgers, "local_numeric_markers_unchanged": True, "math_code_link_labels_excluded": True},
              "figure_interface": {"inline_Markdown_pairs_preserved": 2, "structured_figures_submitted": 0,
                  "note": "Live schema declares optional figures[].data as an unspecified object; no image-data keys are invented. The full PDF is the typeset fallback, separately from API-text preservation."},
              "section_character_counts": caps, "body_regex_words": body_words,
              "body_whitespace_words": sum(len(s["content"].split()) for s in sections), "guideline_checks": guideline_checks,
              "paper_type": "short_communication", "schema_snapshot_sha256": sha(schema_raw),
              "agentpub_payload_sha256": sha(encode(payload)), "AAES_registration_sha256": sha(encode(registration)),
              "AAES_bounded_claims": len(claims), "model_or_token_usage_estimated": False, "unknown_token_sentinel": -1,
              "formal_agent_gates_open": False, "canonical_inputs_unchanged": True,
              "permitted_changes": ["agent front byline/disclosure", "figure routes", "lossless paragraph grouping and four source headings", "AgentPub-only reversible author-year prose markers"],
              "reference_date_provenance_sha256": sha((ROOT / "reproduction/reference-date-provenance.json").read_bytes()), "author_year_disambiguation": "2024a=ID1 original;2024b=ID2 erratum;ID4 year 2022 is the primary commit timestamp", "nonprivate_runtime_locator_allowlist": ["C:/Python 313/python.exe"]}
    readme = f"""# {title}

Agent edition by **{AGENT_NAME}**. Human operator and canonical author: **Taylor Kalin**.

Version {version}. The [canonical manuscript]({CANONICAL_REPOSITORY}/blob/{args.canonical_content_commit}/paper/manuscript.md) retains Taylor's byline. All six scientific bodies, ordered mathematics, ten numbered equations, two original figures/full captions, five references and disclosures remain exact after reversing declared routes/grouping/citations.

- [Complete local agent paper](paper.md)
- [Complete canonical PDF]({CANONICAL_REPOSITORY}/releases/download/v1.0.0/main.pdf)
- [Metadata](metadata.json)
- [Preservation proof](reproduction/adapter-checks.json)
- [Reproduction instructions](reproduction/README.md)
- [Closed-gate context](reproduction/submission-context.json)

This is a source-bound audit of the article, acknowledgement-only erratum and released inputs. Printed growth and normalization discrepancies are distinguished from unknown source simulation/postprocessing behavior. The literal E12 comparison does not establish a universal threshold; the valid variance-one plasma-dispersion convention, positive source arithmetic and stated limits are preserved. Configuration/source-budget witnesses do not measure actual source power or show invalid heating/spectra. No nonlinear source simulation is reproduced.

All **50 computational files** are pinned to H `{args.expected_code_commit}`, distinct tree `{args.expected_code_tree}`. **16 final paper/build/metadata/review-support files** come from release `{args.canonical_content_commit}`. The H README retains its historical computational-only wording; it is not substituted by a later administrative README. Software DOI: https://doi.org/{meta['code_doi']} .

AgentPub uses short_communication with seven lossless groups and reversible author-year citations. The local paper retains numeric citations and the complete canonical bibliography. The two code references use genuine pinned URLs, with no invented DOIs. The original article/erratum use 2024a/b labels; the historical-source year 2022 comes from primary commit metadata, with the basis recorded separately. No science or references are shortened or padded. Exact model/token usage is unknown; -1 is missing data, not a measured count.

**Offline prepared; not formally submitted. Both formal gates remain closed.** This record does not certify this study's own final Publish.fun disposition, eligibility or acceptance. Quota/validation failures, another study's result, a GitHub preprint and a software DOI do not open a formal gate. Internal AI checking is distinct from external human peer review.

Original code is MIT; original text/figures CC BY 4.0. Article-linked input copies retain their upstream MIT notice under reproduction/canonical/third_party/. Historical solver code and source publication PDFs are not redistributed. See [license scope](LICENSE.md). Authorized identity: [{IDENTITY}](https://gist.github.com/Teylersf/7c74312cf47dcc31c789a8b1c3dedd25).
"""
    command = ("python reproduction/prepare_packages.py --outgoing-dir OUTSIDE_PUBLIC_REPOS "
               "--expected-code-commit " + args.expected_code_commit + " --expected-code-tree " + args.expected_code_tree +
               " --canonical-content-commit " + args.canonical_content_commit +
               " --expected-manuscript-sha256 " + sha(md) + " --expected-pdf-sha256 " + sha(pdf) +
               " --expected-input-inventory-sha256 " + sha(inventory_raw))
    reproduction = f"""# Reproduction and preservation

Fifty computational source/code/data/figure/independent-review files are bundled at H `{args.expected_code_commit}`, tree `{args.expected_code_tree}`. Sixteen paper/TeX/build/metadata/software-review files come from release `{args.canonical_content_commit}`. The exact role, revision, bytes and SHA256 of every copy are in pinned-inputs.json. Historical draft-review records remain supporting observations; the final all-page QA binds final paper bytes. The H README is historical. Source article/erratum PDFs and historical solver source are excluded; upstream input files and MIT notice retain their rights.

Run with ordinary Python 3. The adapter is standard-library-only and requires no network, Git, canonical checkout, credentials, target PDF, source solver or scientific producer execution. API bodies must be written outside both repositories.

```text
{command}
```

All 66 copied blobs are verified, including complete 50-file manifest coverage (49+self). Six canonical bodies map in order to seven groups: Introduction: section 1 paragraph 1; Related Work: section 1 paragraphs 2-3; Methodology: section 2; Results: sections 3-4; Discussion: section 5 plus section 6 paragraph 1; Limitations: section 6 paragraphs 2-3; Conclusion: section 6 paragraphs 4-6. Four added source subheadings and image routes are exactly reversible. Full body equality, all ordered mathematics, ten tags, both complete figure/caption pairs, abstract and all five bibliography records are required.

Local paper.md and agent-paper.md retain numeric citations. AgentPub prose alone uses reversible author-year markers with per-occurrence offsets. The same-author article and erratum are 2024a/b; the URL-only input deposit is 2023, and historical solver year 2022 is supported by primary commit metadata in reference-date-provenance.json. No DOI is invented and the complete canonical bibliography remains verbatim in metadata. Mathematical/code/link labels are protected. No text is shortened, no citation added and no word-count padding used.

The cached official schema/instructions are primary format snapshots, not fresh live checks. Short communications allow 1500-4000 body words and require at least five references. Sections are conservatively capped at 49000 UTF16 units. Unknown model/token data are explicitly unrecorded/-1, not estimates. Inline figures link directly to immutable H; the canonical PDF is the typeset fallback. Viewer fidelity is not inferred.

Use canonical/REPRODUCIBILITY.md for the original science and standalone independent verifiers. They are preserved verbatim and are not imported or executed by this adapter. No nonlinear source run, original source output or measured source-power budget is reproduced.

All copied files must retain raw bytes. The immutable copied ignore file hides paper/submissions descendants; later publication must force-add every inventory path and compare all Git/public archive blobs. Do not rewrite frozen attributes or ignores. This script makes no Git mutation.

**Both formal agent gates remain false.** No API call, nonstoring check, eligibility, final Publish.fun disposition or external review is certified by preparation. Root's separate client must verify this study's own final disposition before any formal agent review. Taylor Kalin remains canonical author; authorized agent byline is Lattice Audit Agent with Taylor as human operator. The same MIT/CC BY 4.0/upstream-input scopes apply.
"""
    attrs = "* text=auto eol=lf\n*.json -text\n*.csv -text\n*.png binary\n*.pdf binary\nreproduction/canonical/** -text\nreproduction/canonical/** whitespace=-blank-at-eol\n"
    products = {"paper.md": paper.encode(), "agent-paper.md": paper.encode(), "metadata.json": encode(metadata),
                "README.md": readme.encode(), "reproduction/README.md": reproduction.encode(),
                "reproduction/adapter-checks.json": encode(checks), "reproduction/canonical-preservation-v1.0.0.json": encode(checks),
                "reproduction/submission-context.json": encode(context), ".gitattributes": attrs.encode(),
                ".gitignore": b"__pycache__/\n*.pyc\n.private/\n",
                "LICENSE.md": source["reproduction/canonical/LICENSE.md"]}
    for name, data in products.items():
        safe(name, data)
    if Path(__file__).read_bytes() != SCRIPT_BYTES or (ROOT / "reproduction/agentpub-paper-schema.json").read_bytes() != schema_raw:
        raise ValueError("Adapter/schema changed during preparation")
    if inputs(args)[0] != source:
        raise ValueError("Source bytes changed during preparation")
    for name, data in products.items():
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    outgoing.mkdir(parents=True, exist_ok=True)
    (outgoing / "ion-turbulence-agentpub-payload.json").write_bytes(encode(payload))
    (outgoing / "ion-turbulence-aaes-registration.json").write_bytes(encode(registration))
    assert all((ROOT / name).read_bytes() == data for name, data in products.items())
    print(json.dumps({"prepared": True, "files": 66, "math": len(blocks['math']), "equations": len(tags),
                      "figures": 2, "references": 5, "body_regex_words": body_words,
                      "max_section_UTF16": max(c['UTF16_code_units'] for c in caps.values()),
                      "payload_sha256": checks['agentpub_payload_sha256'], "gates_open": False}))


if __name__ == "__main__":
    main()

