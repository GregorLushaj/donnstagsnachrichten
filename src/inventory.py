"""Task 2.04: inventory of the input data.

Counts Zurich files and issues per year, checks header and emptiness of every
issue file and turns the hand-filled provenance file into the README tables.
Only file names, headers and metadata leave this module, never ad text.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import regex
import yaml

TITLES = ("DN", "ZWB")
EXPECTED_HEADER = "date,page,text,type,category,continuation"
FILENAME_PATTERN = regex.compile(
    r"^(?P<title>DN|ZWB)(?P<date>\d{8})(?:_(?P<suffix>[a-z]))?\.csv$"
)
PROVENANCE_FIELDS = (
    "name",
    "path_key",
    "format",
    "source",
    "date_obtained",
    "access",
    "citation",
)


@dataclass(frozen=True)
class IssueFile:
    name: str
    title: str
    date: date
    supplement: bool


def parse_filename(name: str) -> IssueFile | None:
    """Title, date and supplement flag from e.g. 'DN17300223_b.csv'; None if the name is invalid."""
    match = FILENAME_PATTERN.match(name)
    if match is None:
        return None
    raw = match["date"]
    try:
        issue_date = date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
    except ValueError:
        return None
    return IssueFile(name, match["title"], issue_date, match["suffix"] is not None)


def check_file(path: Path) -> str | None:
    """Problem description for an issue file, None if header and content are fine."""
    if path.stat().st_size == 0:
        return "empty file"
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            header = handle.readline().rstrip("\r\n")
            rest = handle.read(4096)
    except UnicodeDecodeError:
        return "not UTF-8"
    if header != EXPECTED_HEADER:
        return f"wrong header: {header[:80]}"
    if not rest.strip():
        return "header only, no rows"
    return None


def scan_folder(
    folder: Path, start_year: int, end_year: int
) -> tuple[list[IssueFile], pd.DataFrame]:
    """Valid issue files and a table of problems (file, problem) for one folder."""
    files: list[IssueFile] = []
    problems: list[dict[str, str]] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        issue = parse_filename(path.name)
        if issue is None:
            problems.append({"file": path.name, "problem": "invalid file name or date"})
            continue
        if not start_year <= issue.date.year <= end_year:
            problems.append({"file": path.name, "problem": "outside the period"})
        problem = check_file(path)
        if problem is not None:
            problems.append({"file": path.name, "problem": problem})
        files.append(issue)
    return files, pd.DataFrame(problems, columns=["file", "problem"])


def count_per_year(
    files: Iterable[IssueFile], start_year: int, end_year: int
) -> pd.DataFrame:
    """Files and issues per year and title; an issue is a main file merged with its supplements."""
    records = pd.DataFrame(
        [(f.title, f.date, f.date.year, f.supplement) for f in files],
        columns=["title", "date", "year", "supplement"],
    )
    years = pd.Index(range(start_year, end_year + 1), name="year")
    table = pd.DataFrame(index=years)
    for title in TITLES:
        subset = records[records["title"] == title]
        table[f"files_{title}"] = subset.groupby("year").size()
        table[f"issues_{title}"] = (
            subset.drop_duplicates(["title", "date"]).groupby("year").size()
        )
    table["supplements"] = (
        records.loc[records["supplement"].astype(bool)].groupby("year").size()
    )
    table = table.fillna(0).astype(int)
    table["files_total"] = table[[f"files_{t}" for t in TITLES]].sum(axis=1)
    table["issues_total"] = table[[f"issues_{t}" for t in TITLES]].sum(axis=1)
    columns = [f"files_{t}" for t in TITLES] + ["supplements", "files_total"]
    columns += [f"issues_{t}" for t in TITLES] + ["issues_total"]
    return table[columns].reset_index()


def summarise(per_year: pd.DataFrame, problems: pd.DataFrame) -> dict[str, int]:
    """Key figures for output/values/inventory.yml."""
    totals = per_year.drop(columns="year").sum()
    with_files = per_year.loc[per_year["files_total"] > 0, "year"]
    summary = {column: int(value) for column, value in totals.items()}
    summary |= {
        "first_year": int(with_files.min()) if not with_files.empty else 0,
        "last_year": int(with_files.max()) if not with_files.empty else 0,
        "years_without_files": int((per_year["files_total"] == 0).sum()),
        "problems": len(problems),
    }
    return summary


def resolve_path_key(paths: dict, key: str) -> str:
    """Path from config.yml for a dotted key such as 'input.zurich'."""
    value = paths
    for part in key.split("."):
        value = value[part]
    return value


def load_provenance(
    provenance_file: Path, paths: dict, root: Path
) -> tuple[pd.DataFrame, list[str]]:
    """Provenance entries with resolved paths, plus warnings for missing fields and paths."""
    entries = yaml.safe_load(provenance_file.read_text(encoding="utf-8"))["sources"]
    rows: list[dict] = []
    warnings: list[str] = []
    for entry in entries:
        label = entry.get("name", "<unnamed>")
        missing = [field for field in PROVENANCE_FIELDS if not entry.get(field)]
        if missing:
            warnings.append(f"{label}: to fill in: {', '.join(missing)}")
        for point in entry.get("open") or []:
            warnings.append(f"{label}: open: {point}")
        try:
            path = (
                resolve_path_key(paths, entry["path_key"])
                if entry.get("path_key")
                else ""
            )
        except KeyError:
            warnings.append(
                f"{label}: path_key '{entry['path_key']}' not in config.yml"
            )
            path = ""
        present = bool(path) and (root / path).exists()
        if path and not present:
            warnings.append(f"{label}: {path} does not exist")
        rows.append(
            {
                **{field: entry.get(field) or "" for field in PROVENANCE_FIELDS},
                "path": path,
                "present": present,
            }
        )
    return pd.DataFrame(rows), warnings


def dataset_list(provenance: pd.DataFrame) -> pd.DataFrame:
    """README section 'Dataset list' with its column headers."""
    return pd.DataFrame(
        {
            "File or folder": provenance["name"],
            "Source": provenance["source"],
            "Format": provenance["format"],
            "Expected path": provenance["path"],
        }
    )


def data_availability(provenance: pd.DataFrame) -> pd.DataFrame:
    """README section 'Data Availability and Provenance' as a table."""
    return pd.DataFrame(
        {
            "Source": provenance["name"],
            "Obtained": provenance["date_obtained"].astype(str),
            "Access": provenance["access"],
            "Citation": provenance["citation"],
        }
    )
