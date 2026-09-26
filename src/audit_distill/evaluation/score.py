"""Score every mode on the test set: baselines, teacher ceiling, students (CPU only).

Primary score is binary macro-F1 with INVALID as a miss. Uncertainty is a paired
cluster bootstrap over test groups with identical draws for all modes. Report modes
also get automatic grounding/faithfulness checks. Nothing here tunes anything.
"""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from audit_distill.evaluation.predict import EvaluationConfig
from audit_distill.inference import POLARITIES, macro_f1, read_rows
from audit_distill.provenance import file_sha256, project_provenance, write_json
from audit_distill.scoped_reports import ScopedReport, canonical_json, parse_report
from audit_distill.student.dataset import load_student_config
from audit_distill.training.train import load_training_config

logger = logging.getLogger(__name__)
CITATION = re.compile(
    r"\blines?\s+(\d+(?:\s*[-–]\s*\d+)?(?:\s*(?:,|,?\s*and)\s*\d+(?:\s*[-–]\s*\d+)?)*)"
)
ORDERS = {"report": "analysis_first", "report_vf": "verdict_first"}


def code_of(source: str) -> str:
    """The comment-blanked code without its `0001 | ` line prefixes."""
    return "\n".join(line.split("|", 1)[1][1:] for line in source.split("\n"))


def scores(gold: list[str], predicted: list[str]) -> dict[str, object]:
    def count(g: str, p: str) -> int:
        return sum(a == g and b == p for a, b in zip(gold, predicted, strict=True))

    tp, fp = (
        count("PRESENT", "PRESENT"),
        sum(p == "PRESENT" for p in predicted) - count("PRESENT", "PRESENT"),
    )
    positives = gold.count("PRESENT")
    valid = [(g, p) for g, p in zip(gold, predicted, strict=True) if p != "INVALID"]
    return {
        "macro_f1": macro_f1(gold, predicted),
        "present_precision": tp / (tp + fp) if tp + fp else None,
        "present_recall": tp / positives if positives else None,
        "accuracy": sum(g == p for g, p in zip(gold, predicted, strict=True)) / len(gold),
        "invalid": predicted.count("INVALID"),
        "n": len(gold),
        "confusion": {g: {p: count(g, p) for p in (*POLARITIES, "INVALID")} for g in POLARITIES},
        "macro_f1_valid_only": macro_f1([g for g, _ in valid], [p for _, p in valid])
        if valid
        else None,
    }


def bootstrap(
    groups: list[str],
    gold: list[str],
    predictions: dict[str, list[str]],
    comparisons: list[tuple[str, str]],
    config: EvaluationConfig,
) -> dict[str, object]:
    """Percentile 95% intervals from resampled test groups (same draws for every mode)."""
    rng = np.random.default_rng(config.bootstrap_seed)
    members: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        members[group].append(index)
    keys = sorted(members)
    samples: dict[str, list[float]] = defaultdict(list)
    draws = 0
    while (
        len(samples["__valid"]) < config.bootstrap_replicates and draws < config.bootstrap_max_draws
    ):
        draws += 1
        picked = [i for k in rng.choice(len(keys), size=len(keys)) for i in members[keys[k]]]
        g = [gold[i] for i in picked]
        if not all(label in g for label in POLARITIES):
            continue
        samples["__valid"].append(1.0)
        values = {m: macro_f1(g, [p[i] for i in picked]) for m, p in predictions.items()}
        for mode, value in values.items():
            samples[mode].append(value)
        for left, right in comparisons:
            samples[f"{left} - {right}"].append(values[left] - values[right])
    valid = len(samples.pop("__valid", []))
    intervals = {
        name: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
        for name, v in samples.items()
    }
    return {"valid_replicates": valid, "draws": draws, "groups": len(keys), "intervals": intervals}


def grounding(rows: list[dict], raws: list[str], fmt: str, sources: dict[str, str]) -> dict:
    """Cited lines exist and are code; the conclusion states the report's own verdict."""
    cited = on_code = reports = consistent = located = located_on_code = 0
    for row, raw in zip(rows, raws, strict=True):
        try:
            report = parse_report(raw, line_count=row["line_count"], order=ORDERS[fmt])
        except ValueError:
            continue
        reports += 1
        lines = code_of(sources[row["id"]]).split("\n")
        numbers = [
            int(n) for m in CITATION.finditer(report.analysis) for n in re.findall(r"\d+", m[1])
        ]
        cited += len(numbers)
        on_code += sum(1 <= n <= len(lines) and bool(lines[n - 1].strip()) for n in numbers)
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", report.analysis.strip()) if s]
        last = sentences[-1].upper() if sentences else ""
        other = "ABSENT" if report.verdict == "PRESENT" else "PRESENT"
        consistent += report.verdict in last and other not in last
        if report.location:
            located += 1
            span = lines[report.location.start_line - 1 : report.location.end_line]
            located_on_code += any(line.strip() for line in span)
    return {
        "valid_reports": reports,
        "cited_line_numbers": cited,
        "cited_lines_on_code": on_code / cited if cited else None,
        "conclusion_states_own_verdict": consistent / reports if reports else None,
        "locations": located,
        "locations_on_code": located_on_code / located if located else None,
    }


def baselines(config: EvaluationConfig, release: Path) -> dict[str, list[str]]:
    """Floors fitted on the train split only, predicting the test split."""
    train = pq.read_table(release / "train.parquet").to_pylist()
    test = sorted(pq.read_table(release / "test.parquet").to_pylist(), key=lambda r: r["query_id"])

    def majority(key: str) -> list[str]:
        counts: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(POLARITIES, 0))
        for row in train:
            counts[row[key]][row["label"]] += 1
        # Ties (balanced cells) and unseen values fall back to ABSENT.
        return [
            "PRESENT" if counts[r[key]]["PRESENT"] > counts[r[key]]["ABSENT"] else "ABSENT"
            for r in test
        ]

    vectorizer = TfidfVectorizer(
        token_pattern=config.tfidf_token_pattern,
        ngram_range=(1, config.tfidf_ngram_max),
        lowercase=False,
    )
    features = vectorizer.fit_transform([code_of(r["source"]) for r in train])
    classifier = LogisticRegression(C=config.logistic_c, max_iter=2000, random_state=config.seed)
    classifier.fit(features, [r["label"] for r in train])
    tfidf = classifier.predict(vectorizer.transform([code_of(r["source"]) for r in test]))
    return {
        "constant-absent": ["ABSENT"] * len(test),
        "collection-majority": majority("collection"),
        "version-majority": majority("pragma_minor"),
        "tfidf-logreg": [str(p) for p in tfidf],
    }


def evaluate(config: EvaluationConfig, root: Path, split: str = "test") -> dict[str, object]:
    training = load_training_config(config.training_config, root)
    student, teacher, _ = load_student_config(training.student_config, root)
    release = teacher.release_dir
    test = sorted(
        pq.read_table(release / f"{split}.parquet").to_pylist(), key=lambda r: r["query_id"]
    )
    ids = [r["query_id"] for r in test]
    gold = [r["label"] for r in test]
    groups = [r["group_id"] for r in test]
    sources = {r["query_id"]: r["source"] for r in test}
    predictions: dict[str, list[str]] = {}
    details: dict[str, dict] = {}
    prediction_dir = config.predictions_dir / split
    for name, mode in config.modes.items():
        rows = {r["id"]: r for r in read_rows(prediction_dir / f"{name}.jsonl")}
        if sorted(rows) != ids:
            raise ValueError(f"{name} predictions do not cover exactly the {split} queries")
        predictions[name] = [rows[i]["predicted"] for i in ids]
        if mode.format != "label":
            eval_rows = read_rows(student.output_dir / f"{split}_{mode.format}.jsonl")
            by_id = {r["id"]: r for r in eval_rows}
            details[name] = grounding(
                [by_id[i] for i in ids], [rows[i]["raw"] for i in ids], mode.format, sources
            )
    # Teacher ceiling: label-blind verdicts on the same queries (INVALID if none).
    final: dict[str, dict] = {}
    for record in read_rows(config.teacher_ceiling_dir / "items.jsonl"):
        final[record["query_id"]] = record
    if sorted(final) != ids:
        raise ValueError("The teacher ceiling does not cover exactly the test queries")
    predictions["teacher"] = [
        final[i]["verdict"] if final[i]["status"] in ("accepted", "disagreed") else "INVALID"
        for i in ids
    ]
    # Stored records sort keys; rebuild the canonical analysis-first report text.
    teacher_raw = [
        canonical_json(ScopedReport.model_validate(final[i]["report"]), "analysis_first")
        if final[i]["report"]
        else ""
        for i in ids
    ]
    by_id = {r["id"]: r for r in read_rows(student.output_dir / f"{split}_report.jsonl")}
    details["teacher"] = grounding([by_id[i] for i in ids], teacher_raw, "report", sources)
    predictions |= baselines(config, release)

    collections = [r["collection"] for r in test]
    results: dict[str, object] = {"split": split, "n": len(ids), "modes": {}}
    for name, predicted in predictions.items():
        entry = scores(gold, predicted)
        entry["by_collection"] = {
            c: scores(
                [g for g, k in zip(gold, collections, strict=True) if k == c],
                [p for p, k in zip(predicted, collections, strict=True) if k == c],
            )["macro_f1"]
            for c in sorted(set(collections))
        }
        if name in details:
            entry["grounding"] = details[name]
        results["modes"][name] = entry
    results["bootstrap"] = bootstrap(groups, gold, predictions, config.comparisons, config)
    # Same procedure within each collection (RSD is the hard, minimal-pair subset).
    results["bootstrap_by_collection"] = {}
    for c in sorted(set(collections)):
        keep = [i for i, k in enumerate(collections) if k == c]
        results["bootstrap_by_collection"][c] = bootstrap(
            [groups[i] for i in keep],
            [gold[i] for i in keep],
            {m: [p[i] for i in keep] for m, p in predictions.items()},
            config.comparisons,
            config,
        )
    output = config.results_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "predictions").mkdir(exist_ok=True)
    for name, predicted in predictions.items():
        with (output / "predictions" / f"{name}.jsonl").open("w", encoding="utf-8") as stream:
            for qid, g, p in zip(ids, gold, predicted, strict=True):
                stream.write(json.dumps({"id": qid, "gold": g, "predicted": p}) + "\n")
    results["seeds"] = seed_summary(config, split, ids, gold, collections, predictions)
    faith = prediction_dir / "faithfulness.json"
    if faith.is_file():
        results["faithfulness"] = json.loads(faith.read_text(encoding="utf-8"))["modes"]
    results["inputs"] = {
        "predictions_manifest": file_sha256(prediction_dir / "predictions_manifest.json"),
        "teacher_ceiling_usage": file_sha256(config.teacher_ceiling_dir / "usage.json"),
    }
    results["provenance"] = project_provenance(root)
    write_json(output / "metrics.json", results)
    (output / "results.md").write_text(markdown(results, config), encoding="utf-8")
    return results


def seed_summary(
    config: EvaluationConfig,
    split: str,
    ids: list[str],
    gold: list[str],
    collections: list[str],
    predictions: dict[str, list[str]],
) -> dict[str, dict]:
    """Test macro-F1 of each SFT mode across training seeds (main run = config seed)."""
    summary: dict[str, dict] = {}
    for name, mode in config.modes.items():
        if mode.adapter is None:
            continue
        per_seed = {config.seed: predictions[name]}
        for seed in config.extra_seeds:
            path = config.predictions_dir / f"{split}-seed{seed}" / f"{name}.jsonl"
            if path.is_file():
                rows = {r["id"]: r["predicted"] for r in read_rows(path)}
                per_seed[seed] = [rows[i] for i in ids]
        if len(per_seed) < 2:
            continue
        entry: dict[str, object] = {"seeds": sorted(per_seed)}
        for scope in ("all", "aggregated", "rsd"):
            keep = [i for i, c in enumerate(collections) if scope in ("all", c)]
            values = [
                macro_f1([gold[i] for i in keep], [p[i] for i in keep]) for p in per_seed.values()
            ]
            entry[scope] = {
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)),
                "per_seed": dict(zip(sorted(per_seed), values, strict=True)),
            }
        summary[name] = entry
    return summary


def markdown(results: dict, config: EvaluationConfig) -> str:
    intervals = results["bootstrap"]["intervals"]

    def fmt(value: object) -> str:
        return "—" if value is None else f"{value:.3f}"

    lines = [
        f"# Test results ({results['n']} contracts)",
        "",
        "| Mode | Macro-F1 [95% CI] | PRESENT P / R | Accuracy | Invalid | Aggregated | RSD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, m in results["modes"].items():
        low, high = intervals[name]
        lines.append(
            f"| {name} | {m['macro_f1']:.3f} [{low:.3f}, {high:.3f}] | "
            f"{fmt(m['present_precision'])} / {fmt(m['present_recall'])} | {m['accuracy']:.3f} | "
            f"{m['invalid']} | {fmt(m['by_collection'].get('aggregated'))} | "
            f"{fmt(m['by_collection'].get('rsd'))} |"
        )
    by = results["bootstrap_by_collection"]
    lines += [
        "",
        "| Difference | All: point [95% CI] | Aggregated | RSD |",
        "| --- | ---: | ---: | ---: |",
    ]
    for left, right in config.comparisons:
        key = f"{left} - {right}"
        cells = []
        for point, (low, high) in [
            (
                results["modes"][left]["macro_f1"] - results["modes"][right]["macro_f1"],
                intervals[key],
            ),
            *[
                (
                    results["modes"][left]["by_collection"][c]
                    - results["modes"][right]["by_collection"][c],
                    by[c]["intervals"][key],
                )
                for c in ("aggregated", "rsd")
            ],
        ]:
            cells.append(f"{point:+.3f} [{low:+.3f}, {high:+.3f}]")
        lines.append(f"| {left} − {right} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "| Report mode | Valid reports | Cited lines on code | Conclusion states own verdict "
        "| Locations on code |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, m in results["modes"].items():
        g = m.get("grounding")
        if g:
            lines.append(
                f"| {name} | {g['valid_reports']} | {fmt(g['cited_lines_on_code'])} | "
                f"{fmt(g['conclusion_states_own_verdict'])} | {fmt(g['locations_on_code'])} |"
            )
    if results.get("seeds"):
        lines += [
            "",
            "| SFT mode (seeds) | All: mean ± SD | Aggregated | RSD |",
            "| --- | ---: | ---: | ---: |",
        ]
        for name, entry in results["seeds"].items():
            cells = [
                f"{entry[s]['mean']:.3f} ± {entry[s]['sd']:.3f}"
                for s in ("all", "aggregated", "rsd")
            ]
            lines.append(f"| {name} ({len(entry['seeds'])}) | " + " | ".join(cells) + " |")
    if results.get("faithfulness"):
        lines += [
            "",
            "| Faithfulness (analysis-first) | Contracts | Own analysis reproduces verdict "
            "| Empty analysis: accuracy | Swapped analysis: follows donor |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for name, f in results["faithfulness"].items():
            lines.append(
                f"| {name} | {f['contracts']} | {fmt(f['own_reproduces_verdict'])} | "
                f"{fmt(f['empty_accuracy'])} | {fmt(f['swapped_follows_donor'])} "
                f"(n={f['swap_pairs_with_different_verdicts']}) |"
            )
    b = results["bootstrap"]
    groups = ", ".join(f"{c} {v['groups']}" for c, v in by.items())
    lines += [
        "",
        f"Bootstrap: {b['valid_replicates']} valid replicates over {b['groups']} test groups "
        f"({groups}); paired percentile intervals, seed {config.bootstrap_seed}.",
    ]
    return "\n".join(lines) + "\n"
