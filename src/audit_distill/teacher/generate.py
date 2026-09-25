"""Label-blind teacher generation: one query per call, validation, acceptance, resumable records.

Each call shows the teacher exactly one model input (what the student will see) and the
annotation rules, never the label. Each answer is checked mechanically first (schema,
line bounds, token budget); only a valid report is compared with the upstream label.
Agreement is accepted, disagreement is terminal and counted as a label-noise estimate,
and only mechanically invalid or missing output is retried once. Every call and result
is appended to JSONL immediately, so an interrupted run resumes.
"""

import hashlib
import json
import logging
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pyarrow.parquet as pq
import yaml
from pydantic import BaseModel, ConfigDict, Field
from tqdm import tqdm

from audit_distill.config import ConfigModel, TokenizerConfig
from audit_distill.data.release import verify_release
from audit_distill.provenance import digest, file_sha256, project_provenance, write_json
from audit_distill.scoped_reports import (
    ReasonCode,
    canonical_json,
    report_schema,
    teacher_schema,
    unique_keys,
    validate_teacher_report,
)
from audit_distill.teacher.codex import (
    ISOLATION_VERSION,
    CodexHome,
    CodexSettings,
    check_cli,
    invoke,
    preflight,
)

logger = logging.getLogger(__name__)
Split = Literal["train", "validation", "test"]
QUERY_MARKER = "<<QUERY>>"
STATUSES = ("accepted", "disagreed", "unsupported", "invalid", "pending")
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


class TeacherConfig(ConfigModel):
    version: Literal["3.0"]
    release_dir: Path
    release_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_dir: Path
    prompt_path: Path
    schema_path: Path
    codex_version: Literal["0.156.1"]
    model: Literal["gpt-6-sol"]
    reasoning_effort: Literal["medium"]
    verbosity: Literal["low"]
    max_attempts: int = Field(ge=1, le=2)
    timeout_seconds: int = Field(ge=60)
    pilot_per_label: int = Field(ge=1, le=3)
    seed: int

    def codex(self) -> CodexSettings:
        return CodexSettings(
            codex_version=self.codex_version,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            verbosity=self.verbosity,
            timeout_seconds=self.timeout_seconds,
        )


def load_teacher_config(path: Path, root: Path) -> tuple[TeacherConfig, TokenizerConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("release_dir", "output_dir", "prompt_path", "schema_path"):
        data[key] = root / data[key]
    dataset = yaml.safe_load((root / "configs/data.yaml").read_text(encoding="utf-8"))
    return TeacherConfig.model_validate(data), TokenizerConfig.model_validate(dataset["tokenizer"])


class TeacherQuery(BaseModel):
    model_config = ConfigDict(frozen=True)
    query_id: str
    group_id: str
    model_input_sha256: str
    label: Literal["PRESENT", "ABSENT"]
    collection: str
    match_partner: str
    check_id: str
    definition: str
    scope_kind: str
    scope_name: str
    assumptions: list[str]
    source: str

    @property
    def line_count(self) -> int:
        return len(self.source.splitlines())


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["OK", "UNSUPPORTED"]
    report: dict[str, object] | None
    reason_code: ReasonCode | None


def load_split(config: TeacherConfig, split: Split) -> list[TeacherQuery]:
    """Read one cohort from the pinned release and recheck every model-input hash."""
    manifest = verify_release(config.release_dir)
    if manifest["release_content_sha256"] != config.release_content_sha256:
        raise ValueError("Release content differs from the pinned release fingerprint")
    queries = []
    for row in pq.read_table(config.release_dir / f"{split}.parquet").to_pylist():
        payload = {
            "check_id": row["check_id"],
            "definition": row["definition"],
            "scope": {"kind": row["scope_kind"], "name": row["scope_name"]},
            "assumptions": row["assumptions"],
            "source": row["source"],
        }
        if digest(payload) != row["model_input_sha256"]:
            raise ValueError(f"Stale model input: {row['query_id']}")
        queries.append(TeacherQuery.model_validate({k: row[k] for k in TeacherQuery.model_fields}))
    return sorted(queries, key=lambda q: q.query_id)


def pilot_queries(queries: list[TeacherQuery], per_label: int, seed: int) -> list[TeacherQuery]:
    """A few training queries per label in seeded hash order, spread over collections/groups."""
    chosen: list[TeacherQuery] = []
    for label in ("PRESENT", "ABSENT"):
        ranked = sorted(
            (q for q in queries if q.label == label),
            key=lambda q: hashlib.sha256(f"{seed}:{q.query_id}".encode()).hexdigest(),
        )
        picked: list[TeacherQuery] = []
        for fresh_collection in (True, False):
            for query in ranked:
                if len(picked) == per_label:
                    break
                groups = {q.group_id for q in chosen + picked}
                collections = {q.collection for q in picked}
                if query in picked or query.group_id in groups:
                    continue
                if fresh_collection and query.collection in collections:
                    continue
                picked.append(query)
        chosen += picked
    return sorted(chosen, key=lambda q: q.query_id)


def render_prompt(template: str, query: TeacherQuery) -> str:
    """The rules followed by the one model input: check, definition, scope, source."""
    if template.count(QUERY_MARKER) != 1:
        raise ValueError(f"The teacher prompt must contain {QUERY_MARKER} exactly once")
    scope = "the whole file" if query.scope_kind == "FILE" else query.scope_name
    assumptions = "\n".join(f"- {text}" for text in query.assumptions)
    rendered = (
        f"check_id: {query.check_id}\ndefinition: {query.definition}\n"
        f"scope: {query.scope_kind} {scope}\nassumptions:\n{assumptions}\n"
        f"source:\n{query.source}"
    )
    return template.replace(QUERY_MARKER, rendered)


def assess(
    raw: str | None,
    query: TeacherQuery,
    count_tokens: Callable[[str], int],
    max_tokens: int,
) -> dict[str, object]:
    """Mechanical check first (label-blind); only then compare the verdict with the label."""
    try:
        if raw is None:
            raise ValueError("No answer")
        answer = Answer.model_validate(json.loads(raw, object_pairs_hook=unique_keys))
        if answer.status == "UNSUPPORTED":
            if answer.report is not None or answer.reason_code is None:
                raise ValueError("UNSUPPORTED needs a reason code and a null report")
            return {"status": "unsupported", "reason_code": answer.reason_code}
        if answer.report is None or answer.reason_code is not None:
            raise ValueError("OK needs a report and a null reason code")
        report = validate_teacher_report(
            answer.report,
            line_count=query.line_count,
            count_tokens=count_tokens,
            max_tokens=max_tokens,
        )
    except ValueError as error:
        return {"status": "invalid", "error": str(error)[:1000]}
    text = canonical_json(report, "analysis_first")
    return {
        "status": "accepted" if report.verdict == query.label else "disagreed",
        "verdict": report.verdict,
        "report": json.loads(text),
        "report_tokens": count_tokens(text),
    }


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def append_jsonl(path: Path, row: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def now() -> str:
    return datetime.now(UTC).isoformat()


def is_terminal(records: list[dict[str, object]], max_attempts: int) -> bool:
    return bool(records) and (records[-1]["status"] != "invalid" or len(records) >= max_attempts)


def run_settings(config: TeacherConfig, tokenizer: TokenizerConfig) -> dict[str, object]:
    """Everything that defines a teacher output; its digest is the cache identity."""
    if json.loads(config.schema_path.read_text(encoding="utf-8")) != teacher_schema():
        raise ValueError("Stale teacher schema file; run `python -m audit_distill.data.schema`")
    parts = {
        "codex_version": config.codex_version,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "verbosity": config.verbosity,
        "isolation_version": ISOLATION_VERSION,
        "prompt_sha256": file_sha256(config.prompt_path),
        "teacher_schema_sha256": file_sha256(config.schema_path),
        "report_schema_sha256": digest(report_schema()),
        "tokenizer": f"{tokenizer.model_id}@{tokenizer.revision}",
        "max_report_tokens": tokenizer.max_report_tokens,
        "max_attempts": config.max_attempts,
        "release_content_sha256": config.release_content_sha256,
    }
    return parts | {"settings_key": digest(parts)}


def summarize(
    queries: list[TeacherQuery],
    history: dict[str, list[dict[str, object]]],
    invocations: list[dict[str, object]],
    settings: dict[str, object],
    max_attempts: int,
) -> dict[str, object]:
    def status(query: TeacherQuery) -> str:
        records = history.get(query.query_id, [])
        return str(records[-1]["status"]) if is_terminal(records, max_attempts) else "pending"

    statuses = {q.query_id: status(q) for q in queries}
    cells: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for query in queries:
        cells[query.collection][query.label][statuses[query.query_id]] += 1
    counts = Counter(statuses.values())
    judged = counts["accepted"] + counts["disagreed"]
    pairs = [q for q in queries if q.label == "PRESENT" and q.match_partner in statuses]
    reported = [i["usage"] for i in invocations if any(v is not None for v in i["usage"].values())]
    return {
        "settings": settings,
        "queries": len(queries),
        "invocations": len(invocations),
        "invocation_statuses": dict(Counter(str(i["status"]) for i in invocations)),
        "retry_invocations": sum(1 for i in invocations if int(i["attempt"]) > 1),
        "status_counts": {k: counts[k] for k in STATUSES},
        "agreement_rate": counts["accepted"] / judged if judged else None,
        "by_collection_label": {
            c: {label: dict(counter) for label, counter in sorted(labels.items())}
            for c, labels in sorted(cells.items())
        },
        "complete_pairs": sum(
            statuses[q.query_id] == "accepted" == statuses[q.match_partner] for q in pairs
        ),
        "matched_pairs_in_run": len(pairs),
        "tokens": {k: sum(u[k] or 0 for u in reported) for k in USAGE_KEYS},
        "invocations_without_usage": len(invocations) - len(reported),
    }


def load_counter(tokenizer: TokenizerConfig) -> Callable[[str], int]:
    from transformers import AutoTokenizer

    loaded = AutoTokenizer.from_pretrained(
        tokenizer.model_id, revision=tokenizer.revision, trust_remote_code=False
    )
    return lambda text: len(
        loaded.encode(text, add_special_tokens=False, truncation=False, verbose=False)
    )


class TeacherStopped(RuntimeError):
    """The run stopped cleanly (limit, infrastructure failure or invocation cap)."""


def dry_run(
    config: TeacherConfig,
    run_dir: Path,
    queries: list[TeacherQuery],
    template: str,
    count_tokens: Callable[[str], int],
    isolation: dict[str, object],
    max_tokens: int,
) -> dict[str, object]:
    """Zero model calls: counts, invocation ceiling, token estimates and every prompt."""
    prompts_dir = run_dir / "dry-run"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_tokens = []
    for number, query in enumerate(queries, 1):
        prompt = render_prompt(template, query)
        path = prompts_dir / f"{number:03d}_{query.query_id[:12]}.txt"
        path.write_text(prompt, encoding="utf-8")
        prompt_tokens.append(count_tokens(prompt))
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for query in queries:
        counts[query.collection][query.label] += 1
    summary: dict[str, object] = {
        "queries": len(queries),
        "by_collection_label": {c: dict(v) for c, v in sorted(counts.items())},
        "invocations_first_pass": len(queries),
        "invocations_ceiling": len(queries) * config.max_attempts,
        "prompt_tokens": {
            "total": sum(prompt_tokens),
            "max": max(prompt_tokens),
            "note": "Qwen3 tokenizer as a proxy; GPT-6 Sol counts differ somewhat",
        },
        "report_tokens_ceiling": len(queries) * max_tokens,
        "isolation_preflight": isolation,
        "prompts_dir": str(prompts_dir),
    }
    pilot = read_jsonl(config.output_dir / "pilot" / "invocations.jsonl")
    measured = [i["usage"] for i in pilot if i["usage"].get("output_tokens") is not None]
    if measured:
        summary["extrapolated_from_pilot"] = {
            k: round(sum(u[k] or 0 for u in measured) / len(measured) * len(queries))
            for k in USAGE_KEYS
        }
    return summary


def generate(
    config: TeacherConfig,
    tokenizer: TokenizerConfig,
    root: Path,
    split: Split,
    *,
    pilot: bool = False,
    ceiling: bool = False,
    dry: bool = False,
    max_invocations: int | None = None,
) -> dict[str, object]:
    if split == "test" and not ceiling:
        raise ValueError("Test data is teacher-annotated only for the ceiling row (--ceiling)")
    if ceiling and (split != "test" or pilot):
        raise ValueError("--ceiling applies to the test split only")
    if pilot and split != "train":
        raise ValueError("The pilot uses training data only")
    queries = load_split(config, split)
    if pilot:
        queries = pilot_queries(queries, config.pilot_per_label, config.seed)
    run_dir = config.output_dir / ("pilot" if pilot else "test-ceiling" if ceiling else split)
    template = config.prompt_path.read_text(encoding="utf-8")
    settings = run_settings(config, tokenizer)
    count_tokens = load_counter(tokenizer)
    max_tokens = tokenizer.max_report_tokens
    codex = config.codex()
    with CodexHome() as home:
        check_cli(home, codex)
        isolation = preflight(home, codex)
        logger.info("Isolation preflight passed (no model call)")
        if dry:
            return dry_run(config, run_dir, queries, template, count_tokens, isolation, max_tokens)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "events").mkdir(exist_ok=True)
        query_ids = [q.query_id for q in queries]
        run_file = run_dir / "run.json"
        if run_file.is_file():
            previous = json.loads(run_file.read_text(encoding="utf-8"))
            if previous["settings"] != settings or previous["query_ids"] != query_ids:
                raise ValueError(f"{run_dir} holds a run with other settings or queries")
        else:
            write_json(
                run_file,
                {
                    "split": split,
                    "pilot": pilot,
                    "ceiling": ceiling,
                    "settings": settings,
                    "query_ids": query_ids,
                    "isolation_preflight": isolation,
                    "provenance": project_provenance(root),
                    "created_at": now(),
                },
            )
        items_path = run_dir / "items.jsonl"
        invocations_path = run_dir / "invocations.jsonl"
        history: dict[str, list[dict[str, object]]] = defaultdict(list)
        for record in read_jsonl(items_path):
            history[str(record["query_id"])].append(record)
        invocations = read_jsonl(invocations_path)

        def save_usage() -> dict[str, object]:
            summary = summarize(queries, history, invocations, settings, config.max_attempts)
            write_json(run_dir / "usage.json", summary)
            return summary

        spent = 0
        while pending := [
            q for q in queries if not is_terminal(history[q.query_id], config.max_attempts)
        ]:
            for query in tqdm(pending, desc="Teacher calls"):
                if max_invocations is not None and spent >= max_invocations:
                    save_usage()
                    raise TeacherStopped(f"Invocation cap {max_invocations} reached")
                prompt = render_prompt(template, query)
                number = len(invocations) + 1
                attempt = len(history[query.query_id]) + 1
                result = invoke(home, codex, prompt, config.schema_path)
                spent += 1
                (run_dir / "events" / f"{number:04d}.jsonl").write_text(
                    result.events, encoding="utf-8"
                )
                invocation = {
                    "invocation": number,
                    "query_id": query.query_id,
                    "attempt": attempt,
                    "status": result.status,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "usage": result.usage,
                    "tool_items": result.tool_items,
                    "error": result.error,
                    "duration_seconds": round(result.duration_seconds, 1),
                    "settings_key": settings["settings_key"],
                    "created_at": now(),
                }
                append_jsonl(invocations_path, invocation)
                invocations.append(invocation)
                no_answer = result.status == "failed" and result.usage["output_tokens"] is None
                if result.status == "limit" or no_answer:
                    save_usage()
                    raise TeacherStopped(f"Codex call {number} stopped the run: {result.error}")
                outcome = (
                    assess(result.output, query, count_tokens, max_tokens)
                    if result.status == "ok"
                    else {"status": "invalid", "error": result.error}
                )
                record = {
                    "query_id": query.query_id,
                    "split": split,
                    "label": query.label,
                    "collection": query.collection,
                    "match_partner": query.match_partner,
                    "model_input_sha256": query.model_input_sha256,
                    "settings_key": settings["settings_key"],
                    "invocation": number,
                    "attempt": attempt,
                    "verdict": None,
                    "report": None,
                    "reason_code": None,
                    "report_tokens": None,
                    "error": None,
                    "created_at": now(),
                } | outcome
                append_jsonl(items_path, record)
                history[query.query_id].append(record)
                save_usage()
        return save_usage()
