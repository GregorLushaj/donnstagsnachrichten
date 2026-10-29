from datetime import date

import pytest

from src.inventory import (
    EXPECTED_HEADER,
    check_file,
    count_per_year,
    load_provenance,
    parse_filename,
    resolve_path_key,
    scan_folder,
    summarise,
)


@pytest.mark.parametrize(
    ("name", "title", "issue_date", "supplement"),
    [
        ("DN17300215.csv", "DN", date(1730, 2, 15), False),
        ("DN17300223_b.csv", "DN", date(1730, 2, 23), True),
        ("ZWB18420101.csv", "ZWB", date(1842, 1, 1), False),
    ],
)
def test_parse_filename_valid(name, title, issue_date, supplement):
    issue = parse_filename(name)
    assert issue is not None
    assert (issue.title, issue.date, issue.supplement) == (
        title,
        issue_date,
        supplement,
    )


@pytest.mark.parametrize(
    "name",
    [
        "DN17300230.csv",
        "XY17300215.csv",
        "DN1730021.csv",
        "DN17300215.txt",
        "DN17300215_bb.csv",
        "dn17300215.csv",
    ],
)
def test_parse_filename_invalid(name):
    assert parse_filename(name) is None


def write(path, content):
    path.write_text(content, encoding="utf-8")
    return path


def test_check_file(tmp_path):
    assert (
        check_file(
            write(tmp_path / "ok.csv", f"{EXPECTED_HEADER}\nDN17300215,1,x,ad,,0\n")
        )
        is None
    )
    assert (
        check_file(
            write(
                tmp_path / "bom.csv", f"﻿{EXPECTED_HEADER}\r\nDN17300215,1,x,ad,,0\r\n"
            )
        )
        is None
    )
    assert check_file(write(tmp_path / "empty.csv", "")) == "empty file"
    assert (
        check_file(write(tmp_path / "header.csv", f"{EXPECTED_HEADER}\n\n"))
        == "header only, no rows"
    )
    assert check_file(
        write(tmp_path / "wrong.csv", "date,page,text\n1,2,3\n")
    ).startswith("wrong header")
    (tmp_path / "latin.csv").write_bytes(f"{EXPECTED_HEADER}\n\xe4\n".encode("latin-1"))
    assert check_file(tmp_path / "latin.csv") == "not UTF-8"


@pytest.fixture
def folder(tmp_path):
    row = f"{EXPECTED_HEADER}\nX,1,x,ad,,0\n"
    for name in [
        "DN17300215.csv",
        "DN17300223.csv",
        "DN17300223_b.csv",
        "ZWB17320105.csv",
        "ZWB17320108.csv",
    ]:
        write(tmp_path / name, row)
    write(tmp_path / "DN17300230.csv", row)
    write(tmp_path / "DN17310101.csv", "")
    (tmp_path / "subfolder").mkdir()
    return tmp_path


def test_scan_folder_reports_problems(folder):
    files, problems = scan_folder(folder, 1730, 1732)
    assert len(files) == 6
    assert dict(zip(problems["file"], problems["problem"], strict=True)) == {
        "DN17300230.csv": "invalid file name or date",
        "DN17310101.csv": "empty file",
    }


def test_scan_folder_flags_years_outside_period(folder):
    _, problems = scan_folder(folder, 1730, 1731)
    assert set(problems.loc[problems["problem"] == "outside the period", "file"]) == {
        "ZWB17320105.csv",
        "ZWB17320108.csv",
    }


def test_count_per_year_counts_files_and_issues(folder):
    files, problems = scan_folder(folder, 1729, 1733)
    table = count_per_year(files, 1729, 1733).set_index("year")
    assert list(table.index) == [1729, 1730, 1731, 1732, 1733]
    assert table.loc[
        1730, ["files_DN", "supplements", "issues_DN", "issues_total"]
    ].tolist() == [3, 1, 2, 2]
    assert table.loc[1731, "files_DN"] == 1
    assert table.loc[1732, ["files_ZWB", "issues_ZWB", "files_total"]].tolist() == [
        2,
        2,
        2,
    ]
    assert table.loc[1729].sum() == 0

    summary = summarise(table.reset_index(), problems)
    assert summary["files_total"] == 6
    assert summary["issues_total"] == 5
    assert (summary["first_year"], summary["last_year"]) == (1730, 1732)
    assert summary["years_without_files"] == 2
    assert summary["problems"] == 2


def test_count_per_year_without_files():
    table = count_per_year([], 1730, 1731)
    assert table.drop(columns="year").to_numpy().sum() == 0


def test_resolve_path_key():
    paths = {"input": {"zurich": "data/input/zurich"}, "r_script": "reference/x.R"}
    assert resolve_path_key(paths, "input.zurich") == "data/input/zurich"
    assert resolve_path_key(paths, "r_script") == "reference/x.R"


def test_load_provenance_warns_on_gaps(tmp_path):
    (tmp_path / "data").mkdir()
    write(
        tmp_path / "provenance.yaml",
        """
sources:
  - name: Complete
    path_key: input.zurich
    format: csv
    source: OLAT
    date_obtained: 2026-10-15
    access: agreement
    citation: Lab 2026
  - name: Incomplete
    path_key: input.basel
    format: xlsx
    open:
      - confirm the year
  - name: Unknown key
    path_key: input.nowhere
""",
    )
    paths = {"input": {"zurich": "data", "basel": "data/basel"}}
    provenance, warnings = load_provenance(
        tmp_path / "provenance.yaml", paths, tmp_path
    )
    assert provenance["present"].tolist() == [True, False, False]
    assert provenance.loc[0, "date_obtained"] == date(2026, 10, 15)
    assert "Incomplete: to fill in: source, date_obtained, access, citation" in warnings
    assert "Incomplete: data/basel does not exist" in warnings
    assert "Incomplete: open: confirm the year" in warnings
    assert "Unknown key: path_key 'input.nowhere' not in config.yml" in warnings
    assert not any(w.startswith("Complete") for w in warnings)
