import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

from src.datafiles import read_csv, write_csv

ROOT = Path(__file__).resolve().parents[1]


def test_write_csv_format(tmp_path):
    table = pd.DataFrame(
        {
            "date": pd.to_datetime(["1740-01-07", "1740-01-14"]),
            "good": ["Kernen", "Roggen"],
            "price": [1.5, 2.25],
        }
    )
    path = write_csv(table, tmp_path / "sub" / "quotations.csv")
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.decode("utf-8").splitlines() == [
        "date,good,price",
        "1740-01-07,Kernen,1.5",
        "1740-01-14,Roggen,2.25",
    ]


def test_write_csv_python_dates(tmp_path):
    table = pd.DataFrame({"date": [date(1801, 3, 5)]})
    path = write_csv(table, tmp_path / "dates.csv")
    assert path.read_text(encoding="utf-8").splitlines()[1] == "1801-03-05"


def test_round_trip(tmp_path):
    table = pd.DataFrame(
        {"date": pd.to_datetime(["1735-12-29"]), "text": ["Zürich, Mütt"]}
    )
    path = write_csv(table, tmp_path / "round.csv")
    pd.testing.assert_frame_equal(read_csv(path, date_columns=["date"]), table)


def test_data_and_output_are_ignored_by_git():
    """Section 3.4: no file from data/ or output/ may ever reach the repository."""
    probes = ["data/input/zurich/DN17300215.csv", "output/tables/x.csv"]
    result = subprocess.run(
        ["git", "check-ignore", *probes],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.split() == probes
    tracked = subprocess.run(
        ["git", "ls-files", "data", "output"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tracked.stdout == ""
