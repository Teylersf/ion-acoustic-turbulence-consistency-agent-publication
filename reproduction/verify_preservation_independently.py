"""Independent, offline source11 packaging review; never submits or runs science.

Read-only Git cat-file/rev-parse checks occur before the adapter sandbox. The
adapter itself runs in a fresh shadow with audited filesystem, network and
process guards. Run this file first under -O with --optimized-probe, then under
ordinary Python with --optimized-proof pointing to that probe's JSON receipt.
Private payload paths and scratch locations are never written to the public
receipt. No adapter function is imported into the preservation calculations.
"""
from __future__ import annotations
import argparse
import builtins
from collections import Counter
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import pkgutil
import re
import runpy
import shutil
import socket
import subprocess
import sys
import uuid

H = "65f92f1fc9c9419a1240fb9a7c658bb1303aae72"
TREE = "109f70e8192bf1a8bf244b0ca84353e7cd42edf1"
R = "20663439b68d6a81c6e86bbf4bafb2f86034f9a4"
ADAPTER = "46a2ec59612344574e94e29e832f54b2fe6ed3a5a4b4392a66480e49e041a3b8"
INVENTORY = "c97cf88157000b2bc4a99eff788a13f442b888569467fd419bf14cff99b14a90"
MD = "86c0d724b044c98c9dea07be458905702c49e101fd60b1289b39eb9b68d3cc4a"
PDF = "4f9f36f3a0e37687b8d86918980074ddb9a521f2ad30fc1ec2466007c2dd3321"
AP = "29620b7b8ecb82e8835c1875d070968c3c033bde1844023b370cfbd70f676bab"
AAES = "bf7aec17cbf7a08b2012955e99090ebde5445152a3ffc4848d6a32afc0102e0d"
GROUPS = ["Introduction", "Related Work", "Methodology", "Results", "Discussion", "Limitations", "Conclusion"]
LABELS = {"1": "Liu et al., 2024a", "2": "Liu et al., 2024b", "3": "Liu and Gkeyll Team, 2023", "4": "Gkeyll Team, 2022", "5": "Kalin, 2026"}
MATH = re.compile(r"\\\[.*?\\\]|\\\(.*?\\\)|\$\$.*?\$\$|(?<![\\$])\$(?!\$).*?(?<!\\)\$(?!\$)", re.S)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

def require(test, message):
    if not test:
        raise RuntimeError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path):
    return json.loads(path.read_bytes())

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

def section_pairs(text):
    starts = list(re.finditer(r"^## ([^\n]+)$", text, re.M))
    return [(m[1], text[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(text)].strip()) for i, m in enumerate(starts)]

def science_pairs(text):
    pairs = section_pairs(text)
    require(pairs[0][0] == "Abstract" and pairs[-1][0] == "References", "Canonical framing changed")
    numbered = pairs[1:-1]
    require(len(numbered) == 6 and [p[0].split(".", 1)[0] for p in numbered] == list(map(str, range(1, 7))), "Six original bodies required")
    return dict(pairs), numbered

def file_map(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts and "__pycache__" not in p.parts}

def git_blobs(canonical, rows):
    def git(*args, data=None):
        completed = subprocess.run(["git", "-C", str(canonical), *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return completed.stdout
    require(git("rev-parse", H + "^{tree}").decode().strip() == TREE, "H/TREE identity mismatch")
    require(git("rev-parse", R + "^{commit}").decode().strip() == R, "R is not the specified commit")
    queries = [(row["source_revision"] + ":" + row["source_path"]).encode() for row in rows]
    raw = git("cat-file", "--batch", data=b"\n".join(queries) + b"\n")
    stream = io.BytesIO(raw)
    result = []
    for row in rows:
        header = stream.readline().decode().strip().split()
        require(len(header) == 3 and header[1] == "blob", "Missing/nonblob canonical source")
        data = stream.read(int(header[2]))
        require(stream.read(1) == b"\n", "Malformed Git batch output")
        require(len(data) == row["bytes"] and sha(data) == row["sha256"], "Git raw blob differs from inventory: " + row["source_path"])
        result.append({"source_path": row["source_path"], "source_revision": row["source_revision"], "git_blob": header[0], "bytes": len(data), "sha256": sha(data)})
    require(stream.read() == b"", "Unexpected Git output remainder")
    return result

def shadow_run(root, scratch, optimized):
    work = scratch / ("independent-shadow-" + uuid.uuid4().hex)
    shadow = work / "agent-package"
    outgoing = work / "outgoing"
    shadow.mkdir(parents=True)
    auxiliary = ["reproduction/prepare_packages.py", "reproduction/pinned-inputs.json", "reproduction/agentpub-paper-schema.json", "reproduction/agentpub-instructions.txt", "reproduction/reference-date-provenance.json"]
    inventory = read_json(root / "reproduction/pinned-inputs.json")
    names = auxiliary + [row["package_path"] for row in inventory["files"]]
    for name in names:
        src, dst = root / name, shadow / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    before = file_map(shadow)
    forbidden = work / "forbidden-read-probe.txt"
    forbidden.write_text("nonsecret synthetic forbidden-file probe", encoding="utf-8")
    allowed = [shadow.resolve(), outgoing.resolve()]
    guard = {"active": True}
    blocked = {"filesystem": 0, "network": 0, "process": 0}
    def hook(event, args):
        if not guard["active"]:
            return
        if event == "open":
            target = args[0]
            if isinstance(target, (str, bytes, os.PathLike)):
                target = Path(os.fsdecode(target)).resolve()
                if not any(target.is_relative_to(base) for base in allowed):
                    blocked["filesystem"] += 1
                    raise PermissionError("Independent guard: external file access denied")
        if event.startswith("socket."):
            blocked["network"] += 1
            raise PermissionError("Independent guard: network denied")
        if event.startswith("subprocess.") or event in {"os.system", "os.exec", "os.posix_spawn", "os.spawn"}:
            blocked["process"] += 1
            raise PermissionError("Independent guard: subprocess denied")
    sys.addaudithook(hook)
    probes = {}
    saved_argv = sys.argv[:]
    failure = None
    output = io.StringIO()
    try:
        for name, call in [("filesystem", lambda: forbidden.read_bytes()), ("network", lambda: socket.socket()), ("process", lambda: subprocess.Popen(["independent-probe-must-never-launch"]))]:
            try:
                call()
            except PermissionError:
                probes[name] = True
            else:
                raise RuntimeError("Guard failed: " + name)
        sys.argv = [str(shadow / "reproduction/prepare_packages.py"), "--outgoing-dir", str(outgoing),
                    "--expected-code-commit", H, "--expected-code-tree", TREE, "--canonical-content-commit", R,
                    "--expected-manuscript-sha256", MD, "--expected-pdf-sha256", PDF,
                    "--expected-input-inventory-sha256", INVENTORY]
        with contextlib.redirect_stdout(output):
            try:
                runpy.run_path(str(shadow / "reproduction/prepare_packages.py"), run_name="__main__")
            except RuntimeError as exc:
                failure = str(exc)
    finally:
        guard["active"] = False
        sys.argv = saved_argv
    after = file_map(shadow)
    require(all(after.get(name) == digest for name, digest in before.items()), "An isolated input changed")
    if optimized:
        require(sys.flags.optimize > 0 and failure == "Ordinary Python required; -O disables preservation assertions", "Actual optimized adapter rejection failed")
        require(after == before and not outgoing.exists(), "Optimized adapter produced output")
    else:
        require(sys.flags.optimize == 0 and failure is None, "Ordinary isolated adapter failed")
        require(sha((outgoing / "ion-turbulence-agentpub-payload.json").read_bytes()) == AP, "Shadow AgentPub payload differs")
        require(sha((outgoing / "ion-turbulence-aaes-registration.json").read_bytes()) == AAES, "Shadow AAES payload differs")
        for name in ["paper.md", "agent-paper.md", "README.md", "reproduction/README.md", "LICENSE.md", ".gitattributes", ".gitignore"]:
            require((shadow / name).read_bytes() == (root / name).read_bytes(), "Shadow generated product differs: " + name)
        for name in ["metadata.json", "reproduction/adapter-checks.json", "reproduction/canonical-preservation-v1.0.0.json", "reproduction/submission-context.json"]:
            a, b = read_json(shadow / name), read_json(root / name)
            for key in ["prepared_at_utc", "submitted_at"]:
                a.pop(key, None); b.pop(key, None)
            require(a == b, "Shadow generated metadata differs beyond preparation timestamp: " + name)
    return {"status": "passed", "optimized": optimized, "runtime": platform.python_version(), "input_count": len(before),
            "all_inputs_unchanged": True, "all_three_guards_probed": all(probes.values()), "guard_denials": blocked,
            "adapter_network_or_process_calls": blocked["network"] + blocked["process"] - 2,
            "adapter_external_file_reads": blocked["filesystem"] - 1,
            "actual_vault_reads": 0, "science_imports_or_executions": 0,
            "optimized_rejected_before_outputs": optimized, "payloads_exact": not optimized,
            "adapter_sha256": ADAPTER, "inventory_sha256": INVENTORY}

def reverse_citations(text, rows):
    for row in reversed(rows):
        start, end = row["adapted_start"], row["adapted_end"]
        require(text[start:end] == row["adapted"], "Citation offset/text mismatch")
        ids = row["reference_ids"]
        suffix = re.match(r"\[([0-9]+(?:\s*,\s*[0-9]+)*)(,\s*[A-Za-z][^\]]*)?\]", row["canonical"])
        require(suffix is not None and ids == [n.strip() for n in suffix[1].split(",")], "Citation identity mismatch")
        expected = "[" + "; ".join(LABELS[n] for n in ids) + (suffix[2] or "") + "]"
        require(expected == row["adapted"], "Author-year reference map changed")
        text = text[:start] + row["canonical"] + text[end:]
    return text

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--canonical-git", type=Path)
    parser.add_argument("--payload-dir", type=Path)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--optimized-probe", action="store_true")
    parser.add_argument("--optimized-proof", type=Path)
    args = parser.parse_args()
    root = args.package.resolve()
    require(sha((root / "reproduction/prepare_packages.py").read_bytes()) == ADAPTER, "Adapter changed")
    require(sha((root / "reproduction/pinned-inputs.json").read_bytes()) == INVENTORY, "Input inventory changed")
    args.scratch.mkdir(parents=True, exist_ok=True)
    if args.optimized_probe:
        result = shadow_run(root, args.scratch, True)
        write_json(args.scratch / "independent-optimized-probe.json", result)
        print(json.dumps({"optimized_probe": "passed", "inputs": result["input_count"]}))
        return
    require(sys.flags.optimize == 0, "Use ordinary Python for independent preservation checks")
    require(args.canonical_git and args.payload_dir and args.optimized_proof, "Git, private payload and optimized proof arguments required")
    baseline = file_map(root)
    inv = read_json(root / "reproduction/pinned-inputs.json")
    rows = inv["files"]
    require((inv["computational_commit"], inv["computational_tree"], inv["canonical_content_commit"]) == (H, TREE, R), "Mixed pins changed")
    require(len(rows) == 66 and len({r["package_path"] for r in rows}) == 66, "All 66 distinct inputs required")
    for row in rows:
        route = Path(row["package_path"])
        require(not route.is_absolute() and ".." not in route.parts and row["package_path"] == "reproduction/canonical/" + row["source_path"], "Unsafe/altered input route")
        data = (root / route).read_bytes()
        require(sha(data) == row["sha256"] and len(data) == row["bytes"], "Bundled input bytes changed")
    counts = Counter(row["source_revision"] for row in rows)
    require(counts == Counter({H: 50, R: 16}), "50+16 mixed-pin scope changed")
    blobs = git_blobs(args.canonical_git.resolve(), rows)
    manifest = read_json(root / "reproduction/canonical/data/computational-artifact-manifest.json")
    comp = {r["source_path"]: r for r in rows if r["source_revision"] == H}
    require(set(comp) == {r["path"] for r in manifest["files"]} | {"data/computational-artifact-manifest.json"}, "H manifest incomplete")
    require(all(comp[r["path"]]["sha256"] == r["sha256"] for r in manifest["files"]), "H artifact manifest differs")
    md = (root / "reproduction/canonical/paper/manuscript.md").read_bytes()
    pdf = (root / "reproduction/canonical/paper/main.pdf").read_bytes()
    require(sha(md) == MD and sha(pdf) == PDF, "Canonical paper hash changed")
    canonical, original = science_pairs(md.decode())
    science = "\n\n".join(body for _, body in original)
    ap_raw = (args.payload_dir / "ion-turbulence-agentpub-payload.json").read_bytes()
    aaes_raw = (args.payload_dir / "ion-turbulence-aaes-registration.json").read_bytes()
    require(sha(ap_raw) == AP and sha(aaes_raw) == AAES, "Prepared payload hash changed")
    ap, aaes = json.loads(ap_raw), json.loads(aaes_raw)
    checks = read_json(root / "reproduction/adapter-checks.json")
    require([s["heading"] for s in ap["sections"]] == GROUPS, "Seven group order changed")
    route_map = {}
    for _, route in IMAGE.findall(science):
        name = route.rsplit("/", 1)[1]
        route_map["reproduction/canonical/figures/" + name] = route
        route_map["https://raw.githubusercontent.com/Teylersf/ion-acoustic-turbulence-consistency-audit/" + H + "/figures/" + name] = route
    def reverse_routes(text):
        for new, old in route_map.items():
            text = text.replace("](" + new + ")", "](" + old + ")")
        return text
    local, local_original = science_pairs((root / "paper.md").read_text(encoding="utf-8"))
    require((root / "paper.md").read_bytes() == (root / "agent-paper.md").read_bytes(), "Two local agent papers differ")
    require([(h, reverse_routes(b)) for h, b in local_original] == original, "Local six bodies differ")
    require(local["Abstract"] == canonical["Abstract"] and local["References"] == canonical["References"], "Abstract/full bibliography differs")
    require(ap["abstract"] == canonical["Abstract"], "AP abstract differs")
    restored_parts = []
    ledger_count = 0
    for section in ap["sections"]:
        ledger = checks["citation_format"]["reversal_ledger_by_section"][section["heading"]]
        require(section["citations"] == sorted({i for row in ledger for i in row["reference_ids"]}, key=int), "Structured citation IDs differ")
        restored_parts.append(reverse_routes(reverse_citations(section["content"], ledger)))
        ledger_count += len(ledger)
    restored = "\n\n".join(restored_parts)
    for index in [1, 2, 3, 5]:
        marker = "### " + original[index][0] + "\n\n"
        require(restored.count(marker) == 1, "Source subheading missing/ambiguous")
        restored = restored.replace(marker, "", 1)
    require(restored == science, "Regrouped full scientific body is not exactly reversible")
    require(MATH.findall(restored) == MATH.findall(science) and len(MATH.findall(science)) == 83, "83 ordered mathematical spans differ")
    tags = re.findall(r"\\tag\{([^{}]+)\}", restored)
    require(tags == list(map(str, range(1, 11))), "Ten equation tags differ")
    figure_pairs = re.findall(r"(!\[[^\]]*\]\([^)]+\))\n\n(Figure [12]\. [^\n]+)", science)
    require(len(figure_pairs) == 2 and all(image + "\n\n" + caption in restored for image, caption in figure_pairs), "Complete figure/caption pair differs")
    refs = ap["references"]
    require([r["ref_id"] for r in refs] == ["1", "2", "3", "4", "5"], "Five genuine reference identities required")
    require(canonical["References"] in ap["metadata"]["submission_note"], "Complete canonical bibliography missing from metadata")
    for i, ref in enumerate(refs, 1):
        require(ref["title"] in canonical["References"] and ref["url"] in canonical["References"], "Reference title/route invented")
        require(ref["source"] == ("url" if i in [3, 4] else "doi"), "Reference source type mismatch")
        require(("doi" not in ref) if i in [3, 4] else ref["url"] == "https://doi.org/" + ref["doi"], "Invented/mismatched DOI")
    require(refs[2]["year"] == 2023 and "7209ddbfe432b1826df3aa1f7f9fa7f32053a3af/2023_JPP_iat" in refs[2]["url"], "Input reference identity changed")
    require(refs[3]["year"] == 2022 and refs[3]["url"].endswith("69f26286dcc7640024804ba6b1c5ea16d409f759"), "Historical solver identity changed")
    date = read_json(root / "reproduction/reference-date-provenance.json")
    require(date["reference4"]["author_date"] == date["reference4"]["committer_date"] == "2022-05-21T16:48:48Z", "Primary date provenance differs")
    require(ap["authors"] == [{"agent_id": "agent_29b9bf7a", "display_name": "Lattice Audit Agent", "model_type": "not recorded"}], "Authorized agent identity differs")
    require("**Taylor Kalin**" in md.decode().split("## Abstract")[0] and "Human operator and canonical author: **Taylor Kalin**" in (root / "paper.md").read_text(encoding="utf-8"), "Canonical Taylor credit missing")
    meta = read_json(root / "metadata.json")
    require(meta["author_ids"] == ["gist:7c74312cf47dcc31c789a8b1c3dedd25"] and meta["timestamp_scope"] == "local preparation, not registration", "AAES identity/scope mismatch")
    require(ap["metadata"]["total_tokens"] == -1 and ap["metadata"]["agent_model"] == "not recorded", "Unknown usage is not explicit")
    require(aaes["source"] == "github:Teylersf/ion-acoustic-turbulence-consistency-agent-publication" and len(aaes["claims"]) == 5, "AAES route/claim scope changed")
    context = read_json(root / "reproduction/submission-context.json")
    for field in ["AgentPub_submission_gate_open", "AAES_submission_gate_open", "own_Publishfun_final_disposition_verified", "formal_submission_performed", "public_agent_repository_verified"]:
        require(context[field] is False, "False formal/public eligibility claim")
    schema_raw = (root / "reproduction/agentpub-paper-schema.json").read_bytes()
    schema = json.loads(schema_raw)
    limits = schema["paper_types"]["short_communication"]["constraints"]
    body_words = sum(len(re.findall(r"\b[\w'-]+\b", s["content"])) for s in ap["sections"])
    caps = [len(s["content"].encode("utf-16-le")) // 2 for s in ap["sections"]]
    require(ap["paper_type"] == "short_communication" and limits["body_word_count"]["min_words"] <= body_words <= limits["body_word_count"]["max_words"], "Cached paper-type word bounds fail")
    require(len(refs) >= limits["references"]["min_count"] and max(caps) < 49000, "Cached type-specific reference/section bound fails")
    require(all(h in GROUPS for h in limits["sections"]["required"]), "Missing required type-specific section")
    optimized = read_json(args.optimized_proof)
    require(optimized["optimized"] is True and optimized["optimized_rejected_before_outputs"] is True and optimized["adapter_sha256"] == ADAPTER and optimized["inventory_sha256"] == INVENTORY, "Missing bound actual -O proof")
    shadow = shadow_run(root, args.scratch, False)
    require(file_map(root) == baseline, "Original package changed during review")
    result = {"status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(), "review_type": "Independent internal AI packaging/preservation check; not human peer review or scientific rerun",
              "verifier_sha256": sha(Path(__file__).read_bytes()), "adapter_sha256": ADAPTER, "pinned_inventory_sha256": INVENTORY,
              "computational_commit": H, "computational_tree": TREE, "canonical_content_commit": R,
              "canonical_manuscript_sha256": MD, "canonical_pdf_sha256": PDF, "agentpub_payload_sha256": AP, "AAES_registration_sha256": AAES,
              "raw_canonical_git_blobs_verified": blobs, "mixed_pin_counts": {"computational": 50, "paper_build_metadata_review_support": 16, "total": 66},
              "complete_computational_manifest_verified": True, "six_original_bodies_exact": True, "seven_platform_groups_exactly_reversible": True,
              "all_scientific_text_order_exact": True, "abstract_exact": True, "full_bibliography_verbatim": True, "math_segments_ordered": 83,
              "numbered_equation_tags": tags, "full_figure_caption_pairs": 2, "references": 5, "citation_reversal_occurrences": ledger_count,
              "article_erratum_2024a_b_reversible": True, "code_references_legitimate_URL_only": True, "reference4_year_basis": "Primary historical commit author/committer timestamp 2022-05-21, not a guessed publication year",
              "Taylor_canonical_and_authorized_agent_byline": True, "unknown_usage_not_estimated": True,
              "cached_paper_type_constraints": {"paper_type": "short_communication", "body_regex_words": body_words, "body_word_bounds": limits["body_word_count"], "minimum_references": limits["references"]["min_count"], "max_section_UTF16": max(caps), "passed": True, "schema_sha256": sha(schema_raw), "scope": "Cached type-specific constraints; generic schema contains research-article defaults. No live API validation or unknown sentinel acceptance is certified."},
              "ordinary_shadow_run": shadow, "optimized_shadow_run": optimized, "package_inputs_unchanged": True,
              "both_formal_gates_closed": True, "formal_submissions": 0, "API_calls": 0, "network_requests": 0, "vault_reads": 0, "scientific_producer_imports_or_runs": 0, "git_mutations": 0,
              "git_read_only_operations": ["rev-parse H tree", "rev-parse R commit", "cat-file --batch 66 raw blobs"],
              "scope_limits": ["No acceptance, public agent repository, eligibility or final Publish.fun disposition is inferred.", "Inline mathematical/figure text preservation does not certify AgentPub viewer rendering; full canonical PDF remains the typeset fallback.", "Full original code/data/review copies remain unchanged; no source simulation or source-power measurement is reproduced."]}
    write_json(root / "reproduction/independent-preservation-checks.json", result)
    print(json.dumps({"status": "passed", "copied_files": 66, "math": 83, "tags": 10, "figures": 2, "references": 5, "citation_reversals": ledger_count, "body_regex_words": body_words, "max_section_UTF16": max(caps), "receipt_sha256": sha((root / "reproduction/independent-preservation-checks.json").read_bytes())}))

if __name__ == "__main__":
    main()
