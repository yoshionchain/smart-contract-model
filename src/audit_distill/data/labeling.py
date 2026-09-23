"""Interactive human label review for the v2.2 release queues.

Each card is shown blind first (exactly the model input), the reviewer records an
initial verdict, and only then is the upstream evidence revealed. Decisions are
appended to a local JSONL file after every card, so a session can stop at any time.
This tool records a human's decisions; it never proposes or fills in a label.
"""

import argparse
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pyarrow.parquet as pq
from pydantic import Field, model_validator

from audit_distill.data.candidates import ASSUMPTIONS, canonical_payload
from audit_distill.data.records import Artifact, CandidateQuery
from audit_distill.data.release import ReleaseQuery, ReleaseRecord, verify_release
from audit_distill.data.scopes import digest

Queue = Literal["training_audit", "primary_test"]
Verdict = Literal["PRESENT", "ABSENT", "UNKNOWN"]
QUEUE_FILES: dict[Queue, str] = {
    "training_audit": "review_queue_audit.jsonl",
    "primary_test": "review_queue_primary.jsonl",
}


class LabelReview(ReleaseRecord):
    """One signed human decision. Only a person may create these records."""

    queue: Queue
    query_id: str
    input_sha256: str
    reviewer: str = Field(min_length=1, pattern=r"\S")
    reviewer_kind: Literal["human"]
    reviewed_at: str = Field(min_length=1)
    initial_verdict: Verdict
    upstream_verdict: Literal["PRESENT", "ABSENT"]
    final_verdict: Verdict
    input_sufficient: bool
    check_equivalent: bool
    assumptions: list[str]
    vulnerable_lines: list[int]
    evidence_references: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1, pattern=r"\S")

    @model_validator(mode="after")
    def consistent(self) -> "LabelReview":
        if self.final_verdict != "UNKNOWN" and not (
            self.input_sufficient and self.check_equivalent
        ):
            raise ValueError("A PRESENT/ABSENT decision requires sufficient, equivalent input")
        if self.vulnerable_lines and self.final_verdict != "PRESENT":
            raise ValueError("Vulnerable lines are recorded only for a final PRESENT verdict")
        if any(line < 1 for line in self.vulnerable_lines):
            raise ValueError("Vulnerable lines are one-based")
        return self

    @property
    def accepted(self) -> bool:
        return self.final_verdict != "UNKNOWN"


def query_card(directory: Path, query_id: str, *, reveal: bool = False) -> dict[str, object]:
    """Build the exact blind model input and, only if asked, the native evidence."""
    rows = pq.read_table(
        directory / "queries.parquet", filters=[("query_id", "=", query_id)]
    ).to_pylist()
    if len(rows) != 1:
        raise ValueError(f"Expected one candidate for query {query_id}")
    query = CandidateQuery.model_validate(rows[0])
    artifacts = pq.read_table(
        directory / "artifacts.parquet", filters=[("artifact_id", "=", query.artifact_id)]
    ).to_pylist()
    artifact = Artifact.model_validate(artifacts[0])
    taxonomy = json.loads((directory / "taxonomy.json").read_text(encoding="utf-8"))
    payload = canonical_payload(
        artifact, query.check_id, taxonomy["checks"][query.check_id]["definition"], query.scope
    )
    if digest(payload) != query.model_input_sha256:
        raise ValueError("Stale query input hash")
    card: dict[str, object] = {
        "query_id": query.query_id,
        "input_sha256": query.model_input_sha256,
        "model_input": payload,
    }
    if reveal:
        evidence = pq.read_table(
            directory / "assessments.parquet",
            filters=[("assessment_id", "in", query.assessment_ids)],
        ).to_pylist()
        for row in evidence:
            row["metadata"] = dict(row["metadata"])
        card["native_evidence"] = evidence
    return card


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_reviews(path: Path, release: Path) -> list[LabelReview]:
    """Validate recorded decisions against the fixed queues and exact reviewed inputs."""
    queues = {
        queue: {row["query_id"]: row for row in read_jsonl(release / name)}
        for queue, name in QUEUE_FILES.items()
    }
    reviews: list[LabelReview] = []
    seen: set[tuple[str, str]] = set()
    for row in read_jsonl(path):
        review = LabelReview.model_validate(row)
        key = (review.queue, review.query_id)
        if key in seen:
            raise ValueError(f"Duplicate review decision: {review.query_id}")
        seen.add(key)
        entry = queues[review.queue].get(review.query_id)
        if entry is None or entry["input_sha256"] != review.input_sha256:
            raise ValueError(f"Review is not for a current queue item/input: {review.query_id}")
        reviews.append(review)
    return reviews


def next_item(
    queue: Queue, entries: list[dict[str, object]], reviews: list[LabelReview], quota: int
) -> dict[str, object] | None:
    done = {r.query_id for r in reviews if r.queue == queue}
    accepted = Counter(r.final_verdict for r in reviews if r.queue == queue and r.accepted)
    for entry in sorted(entries, key=lambda e: int(e["presentation_order"])):
        if entry["query_id"] in done:
            continue
        # The primary queue stops drawing a polarity once its reviewed quota is met.
        if queue == "primary_test" and accepted[str(entry["polarity_queue"])] >= quota:
            continue
        return entry
    return None


def parse_lines(text: str, line_count: int) -> list[int]:
    lines: set[int] = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        low, _, high = part.partition("-")
        start, end = int(low), int(high or low)
        if not 1 <= start <= end <= line_count:
            raise ValueError(f"Line range {part} is outside 1..{line_count}")
        lines.update(range(start, end + 1))
    return sorted(lines)


def ask(prompt: str, choices: dict[str, str]) -> str:
    keys = "/".join(choices)
    while True:
        answer = input(f"{prompt} [{keys}]: ").strip().lower()
        if answer in choices:
            return choices[answer]
        if answer == "q":
            raise KeyboardInterrupt
        print(f"  Please answer one of: {keys} (q quits; progress is saved per card)")


def blind_text(card: dict[str, object], query: ReleaseQuery, position: str) -> str:
    payload = card["model_input"]
    return "\n".join(
        [
            f"# Review card {position}",
            "",
            f"- Check: {payload['check_id']} — {payload['definition']}",
            f"- Scope: {query.scope_kind} `{query.scope_name}` "
            f"(lines {query.scope_start_line}–{query.scope_end_line})",
            f"- Assumptions: {' '.join(payload['assumptions'])}",
            "",
            "Decide from this source alone before revealing the upstream evidence.",
            "",
            "```solidity",
            str(payload["source"]),
            "```",
            "",
        ]
    )


def evidence_text(card: dict[str, object], query: ReleaseQuery) -> tuple[str, list[str]]:
    lines = [
        "## Revealed upstream evidence",
        "",
        f"- Upstream verdict: **{query.upstream_verdict}**",
        f"- Original collection(s): {query.collection}",
    ]
    references: list[str] = []
    for row in card["native_evidence"]:
        lines += [
            "",
            f"### {row['native_property']} = {row['native_verdict']} ({row['evidence_tier']})",
            f"- Native scope: {row['native_scope_kind']} {row['native_scope']}",
            f"- Native lines (own artifact): {row['native_lines'] or 'none recorded'}",
            f"- Reference: {row['evidence_reference']}",
            f"- Annotation: {row['annotation_path']} #{row['native_id']}",
        ]
        if row["rationale"].strip(" -"):
            lines.append(f"- Upstream note: {row['rationale']}")
        references.append(f"{row['annotation_path']}#{row['native_id']}")
        references.append(str(row["evidence_reference"]))
    lines += [
        "",
        "Check: same reentrancy property and scope? Is the supplied file sufficient "
        "(no missing imports/guards that decide it)? Does the code support the label?",
        "",
    ]
    return "\n".join(lines), sorted(set(references))


def review_card(
    entry: dict[str, object],
    query: ReleaseQuery,
    queue: Queue,
    dataset: Path,
    card_path: Path,
    reviewer: str,
    position: str,
) -> LabelReview:
    card = query_card(dataset, query.query_id, reveal=True)
    if card["input_sha256"] != entry["input_sha256"]:
        raise ValueError("Queue input hash differs from the inventory model input")
    blind = blind_text(card, query, position)
    card_path.write_text(blind, encoding="utf-8")
    source_lines = str(card["model_input"]["source"]).count("\n") + 1
    print(f"\n=== Card {position} ({queue}) ===")
    print(f"Open {card_path} to read the blind input ({source_lines} lines).")
    span = f"{query.scope_start_line}-{query.scope_end_line}"
    print(f"Scope: {query.scope_kind} {query.scope_name} lines {span}")
    verdicts = {"p": "PRESENT", "a": "ABSENT", "u": "UNKNOWN"}
    initial = ask("Blind verdict: present / absent / unknown", verdicts)
    revealed, references = evidence_text(card, query)
    card_path.write_text(blind + "\n" + revealed, encoding="utf-8")
    print("\n" + revealed)
    final = ask("Final verdict after the evidence", verdicts)
    yes_no = {"y": True, "n": False}
    sufficient = ask("Is the supplied source sufficient to decide?", yes_no)
    equivalent = ask("Is the upstream property the same reentrancy check/scope?", yes_no)
    if final != "UNKNOWN" and not (sufficient and equivalent):
        print("  Insufficient or non-equivalent input is recorded as UNKNOWN.")
        final = "UNKNOWN"
    vulnerable: list[int] = []
    if final == "PRESENT":
        while True:
            text = input("Vulnerable lines you verified (e.g. 42-47,50; empty if none): ")
            try:
                vulnerable = parse_lines(text, source_lines)
                break
            except ValueError as error:
                print(f"  {error}")
    rationale = ""
    while not rationale.strip():
        rationale = input("One-sentence rationale: ").strip()
    return LabelReview(
        queue=queue,
        query_id=query.query_id,
        input_sha256=str(entry["input_sha256"]),
        reviewer=reviewer,
        reviewer_kind="human",
        reviewed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        initial_verdict=initial,
        upstream_verdict=query.upstream_verdict,
        final_verdict=final,
        input_sufficient=sufficient,
        check_equivalent=equivalent,
        assumptions=list(ASSUMPTIONS),
        vulnerable_lines=vulnerable,
        evidence_references=references,
        rationale=rationale,
    )


def progress(queue: Queue, entries: list[dict[str, object]], reviews: list[LabelReview]) -> str:
    mine = [r for r in reviews if r.queue == queue]
    accepted = Counter(r.final_verdict for r in mine if r.accepted)
    changed = sum(r.accepted and r.final_verdict != r.upstream_verdict for r in mine)
    return (
        f"{queue}: {len(mine)}/{len(entries)} reviewed; accepted PRESENT {accepted['PRESENT']}, "
        f"ABSENT {accepted['ABSENT']}; UNKNOWN {sum(not r.accepted for r in mine)}; "
        f"corrected {changed}"
    )


def default_reviewer() -> str:
    try:
        return subprocess.check_output(["git", "config", "user.name"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", choices=["audit", "primary"], help="Which fixed queue to review")
    parser.add_argument("--release", type=Path, default=Path("data/processed/reentrancy-v2.2"))
    parser.add_argument("--inventory", type=Path, default=Path("data/processed/reentrancy-v2.1"))
    parser.add_argument("--reviews", type=Path, default=Path("data/reviews/reentrancy-v2.2.jsonl"))
    parser.add_argument("--card", type=Path, default=Path("data/reviews/current_card.md"))
    parser.add_argument("--reviewer", default=default_reviewer(), help="Your name (human only)")
    parser.add_argument("--status", action="store_true", help="Show progress and exit")
    args = parser.parse_args()
    queue: Queue = "training_audit" if args.queue == "audit" else "primary_test"
    try:
        manifest = verify_release(args.release)
        entries = read_jsonl(args.release / QUEUE_FILES[queue])
        queries = {
            row["query_id"]: ReleaseQuery.model_validate(row)
            for row in read_jsonl(args.release / "release_queries.jsonl")
        }
        quota = int(
            json.loads((args.release / "effective_release_config.json").read_text())[
                "primary_per_polarity"
            ]
        )
        args.reviews.parent.mkdir(parents=True, exist_ok=True)
        reviews = load_reviews(args.reviews, args.release)
        release_id = manifest["release_content_sha256"][:12]
        print(f"Release {release_id} — {progress(queue, entries, reviews)}")
        if args.status:
            return
        if not args.reviewer.strip():
            parser.error("Pass --reviewer with your name")
        while (entry := next_item(queue, entries, reviews, quota)) is not None:
            done = sum(r.queue == queue for r in reviews)
            review = review_card(
                entry,
                queries[str(entry["query_id"])],
                queue,
                args.inventory,
                args.card,
                args.reviewer.strip(),
                f"{done + 1}/{len(entries)}",
            )
            with args.reviews.open("a", encoding="utf-8") as stream:
                stream.write(review.model_dump_json() + "\n")
            reviews.append(review)
            print(f"Saved. {progress(queue, entries, reviews)}")
        print("Queue complete.")
    except KeyboardInterrupt:
        print("\nStopped. Every completed card is saved; rerun the same command to continue.")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Review stopped: {error}\n")
