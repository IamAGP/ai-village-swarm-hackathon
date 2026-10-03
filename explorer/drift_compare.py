"""Compare frozen independent drift labels by row ID, without changing either set.

Run beside private JSONL inputs. Outputs are aggregate statistics, never chat text.
Bootstrap intervals resample messages and do not account for cascade dependence.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random


STANCES = ("original", "repeats", "amplifies", "hedges", "checks", "flags", "neutral")


@dataclass(frozen=True)
class LabelSet:
    records: dict

    @classmethod
    def from_records(cls, records):
        indexed = {}
        for record in records:
            row_id = record["msg_id"]
            if row_id in indexed:
                raise ValueError(f"Duplicate row ID: {row_id}")
            if record.get("stance") not in STANCES:
                raise ValueError(f"Unknown stance for {row_id}")
            indexed[row_id] = dict(record)
        if not indexed:
            raise ValueError("Empty label set")
        return cls(indexed)

    @classmethod
    def read(cls, paths):
        return cls.from_records(
            json.loads(line)
            for path in paths
            for line in Path(path).read_text().splitlines()
            if line.strip()
        )

    def validate_items(self, paths):
        items = {}
        for path in paths:
            for line in Path(path).read_text().splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                if item["msg_id"] in items:
                    raise ValueError("Duplicate input row ID")
                items[item["msg_id"]] = item
        if items.keys() != self.records.keys():
            raise ValueError("Input and label row IDs differ")
        for row_id, label in self.records.items():
            item = items[row_id]
            if label.get("agent") != item["agent"]:
                raise ValueError(f"Agent mismatch for {row_id}")
            cue = label.get("cue", "")
            if not cue or len(cue.split()) > 12 or cue not in item["text"]:
                raise ValueError(f"Invalid excerpt cue for {row_id}")
            gist = label.get("gist", "")
            if not gist or len(gist.split()) > 14:
                raise ValueError(f"Invalid gist for {row_id}")


def kappa(pairs):
    n = len(pairs)
    if not n:
        raise ValueError("No paired labels")
    a = Counter(x for x, _ in pairs)
    b = Counter(y for _, y in pairs)
    observed = sum(x == y for x, y in pairs) / n
    expected = sum(a[s] * b[s] for s in STANCES) / n**2
    return (observed - expected) / (1 - expected) if expected < 1 else None


def wilson(successes, n):
    z = 1.959963984540054
    proportion = successes / n
    divisor = 1 + z*z/n
    center = (proportion + z*z/(2*n)) / divisor
    half = z * math.sqrt(proportion*(1-proportion)/n + z*z/(4*n*n)) / divisor
    return [center - half, center + half]


def compare(primary, reference, *, bootstrap=10000, seed=28):
    if primary.records.keys() != reference.records.keys():
        raise ValueError("Label sets must cover exactly the same row IDs")
    if bootstrap < 0:
        raise ValueError("Bootstrap count must be nonnegative")
    pairs = []
    matrix = {a: {b: 0 for b in STANCES} for a in STANCES}
    disagreements = []
    for row_id in sorted(primary.records):
        a, b = primary.records[row_id], reference.records[row_id]
        if a.get("agent") != b.get("agent"):
            raise ValueError(f"Annotator agent mismatch for {row_id}")
        x, y = a["stance"], b["stance"]
        pairs.append((x, y))
        matrix[x][y] += 1
        if x != y:
            disagreements.append({"msg_id": row_id, "primary": x, "reference": y,
                                  "targeted": bool({x, y} & {"amplifies", "flags"})})
    n = len(pairs)
    agreements = sum(x == y for x, y in pairs)
    rng = random.Random(seed)
    draws = [kappa(rng.choices(pairs, k=n)) for _ in range(bootstrap)]
    valid = sorted(x for x in draws if x is not None)
    # Empirical order statistics, with no interpolation.
    interval = ([valid[max(0, math.ceil(.025*len(valid))-1)],
                 valid[max(0, math.ceil(.975*len(valid))-1)]] if valid else None)
    return {
        "n": n, "agreements": agreements, "agreement": agreements/n,
        "agreement_wilson_ci95": wilson(agreements, n), "kappa": kappa(pairs),
        "kappa_bootstrap_ci95": interval, "bootstrap": bootstrap, "seed": seed,
        "undefined_bootstrap_draws": len(draws)-len(valid),
        "ci_caveat": "Messages resampled iid; cascade dependence is not accounted for.",
        "primary_counts": {s: sum(x == s for x, _ in pairs) for s in STANCES},
        "reference_counts": {s: sum(y == s for _, y in pairs) for s in STANCES},
        "stances": STANCES, "matrix_primary_rows_reference_columns": matrix,
        "disagreements": disagreements,
        "targeted_disagreements": sum(d["targeted"] for d in disagreements),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path, nargs="+")
    parser.add_argument("--items", type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=28)
    parser.add_argument("--frozen-sha256", help="Check primary bytes against the pre-comparison freeze")
    args = parser.parse_args()
    digest = hashlib.sha256(args.primary.read_bytes()).hexdigest()
    if args.frozen_sha256 and digest != args.frozen_sha256:
        parser.error("Primary labels differ from the frozen hash")
    primary = LabelSet.read([args.primary])
    reference = LabelSet.read(args.reference)
    if args.items:
        primary.validate_items(args.items)
    report = compare(primary, reference, bootstrap=args.bootstrap, seed=args.seed)
    report["primary_sha256"] = digest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                     ("n", "agreements", "kappa", "kappa_bootstrap_ci95", "targeted_disagreements")}))


if __name__ == "__main__":
    main()
