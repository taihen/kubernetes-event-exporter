#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


PASS_MARK = "✅"
FAIL_MARK = "❌"
BLANK_MARK = ""
HEADER = "kubernetes-event-exporter"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions-file", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--row-label", required=True)
    parser.add_argument("--matrix-file", required=True)
    return parser.parse_args()


def load_versions(path: Path):
    raw = json.loads(path.read_text())
    return [item["k8s_version"] for item in raw]


def load_results(path: Path):
    results = {}
    if not path.exists():
        return results

    for file_path in sorted(path.glob("*.json")):
        raw = json.loads(file_path.read_text())
        results[raw["k8s_version"]] = PASS_MARK if raw["status"] == "pass" else FAIL_MARK
    return results


def parse_existing_rows(matrix_path: Path):
    if not matrix_path.exists():
        return []

    rows = []
    for line in matrix_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] in {HEADER, "---"}:
            continue
        rows.append((cells[0], cells[1:]))
    return rows


def build_row_map(existing_rows, versions):
    row_map = {}
    row_order = []

    for label, cells in existing_rows:
        row_order.append(label)
        padded = list(cells[: len(versions)])
        if len(padded) < len(versions):
            padded.extend([BLANK_MARK] * (len(versions) - len(padded)))
        row_map[label] = padded

    return row_map, row_order


def ensure_row(row_label, row_map, row_order, versions):
    if row_label in row_map:
        return

    row_map[row_label] = [BLANK_MARK] * len(versions)
    if row_label == "master":
        row_order.insert(0, row_label)
    else:
        row_order.append(row_label)


def update_row(row_label, row_map, versions, results):
    row = row_map[row_label]
    for idx, version in enumerate(versions):
        if version in results:
            row[idx] = results[version]


def render_table(row_order, row_map, versions):
    lines = [
        "# Kubernetes compatibility matrix",
        "",
        "This table is updated by GitHub Actions.",
        "",
        f"| {HEADER} | " + " | ".join(versions) + " |",
        "| --- | " + " | ".join(["---"] * len(versions)) + " |",
    ]

    for label in row_order:
        row = row_map[label]
        lines.append(f"| {label} | " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "- Rows are `kubernetes-event-exporter` versions.",
            "- Columns are Kubernetes minor versions.",
            "- A blank cell means that version has not been tested for that exporter row yet.",
        ]
    )

    return "\n".join(lines) + "\n"


def main():
    args = parse_args()

    versions = load_versions(Path(args.versions_file))
    results = load_results(Path(args.results_dir))
    existing_rows = parse_existing_rows(Path(args.matrix_file))
    row_map, row_order = build_row_map(existing_rows, versions)
    ensure_row(args.row_label, row_map, row_order, versions)
    update_row(args.row_label, row_map, versions, results)

    Path(args.matrix_file).write_text(render_table(row_order, row_map, versions))


if __name__ == "__main__":
    main()
