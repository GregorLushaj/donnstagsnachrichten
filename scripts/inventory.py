"""Task 2.04: record files and issues per year and the provenance of the input data.

Standalone check of data/input/, not part of run_all.py (decision E16).
Run with: uv run python scripts/inventory.py
Exits with 1 if a Zurich file has an invalid name, a wrong header or no content.
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import inventory  # noqa: E402
from src.datafiles import write_csv  # noqa: E402


def write_table(table, stem: Path) -> None:
    write_csv(table, stem.with_suffix(".csv"))
    stem.with_suffix(".md").write_text(
        table.to_markdown(index=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.yml")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    paths = config["paths"]
    start_year = int(config["period"]["start"][:4])
    end_year = int(config["period"]["end"][:4])
    tables = ROOT / paths["tables"]
    values = ROOT / paths["values"]
    tables.mkdir(parents=True, exist_ok=True)
    values.mkdir(parents=True, exist_ok=True)

    files, problems = inventory.scan_folder(
        ROOT / paths["input"]["zurich"], start_year, end_year
    )
    per_year = inventory.count_per_year(files, start_year, end_year)
    summary = inventory.summarise(per_year, problems)

    provenance, warnings = inventory.load_provenance(
        ROOT / paths["provenance"], paths, ROOT
    )
    summary["provenance_warnings"] = len(warnings)
    summary["inputs_present"] = {
        row.path_key: bool(row.present) for row in provenance.itertuples()
    }

    write_table(per_year, tables / "tbl-files-per-year")
    write_csv(problems, tables / "inventory_problems.csv")
    write_table(inventory.dataset_list(provenance), tables / "tbl-dataset-list")
    write_table(
        inventory.data_availability(provenance), tables / "tbl-data-availability"
    )
    (values / "inventory.yml").write_text(
        yaml.safe_dump(summary, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    print(
        f"Zurich: {summary['files_total']} files, {summary['issues_total']} issues, "
        f"{summary['first_year']} to {summary['last_year']}, "
        f"{summary['years_without_files']} years without files"
    )
    for warning in warnings:
        print(f"provenance: {warning}")
    for row in problems.itertuples():
        print(f"problem: {row.file}: {row.problem}")
    print(f"written to {tables.relative_to(ROOT)} and {values.relative_to(ROOT)}")
    return 1 if summary["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
