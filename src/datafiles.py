"""Task 2.05: one format for all intermediate and analysis files (section 3.4).

Every table that a step writes to data/ or output/tables/ goes through
write_csv: csv, UTF-8 without BOM, LF line endings, no index, dates in ISO
format. read_csv reads such a file back with the date columns parsed.
"""

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

ENCODING = "utf-8"
DATE_FORMAT = "%Y-%m-%d"


def write_csv(table: pd.DataFrame, path: Path) -> Path:
    """Write a table in the project format; creates the folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(
        path,
        index=False,
        encoding=ENCODING,
        lineterminator="\n",
        date_format=DATE_FORMAT,
    )
    return path


def read_csv(path: Path, date_columns: Iterable[str] = ()) -> pd.DataFrame:
    """Read a table written by write_csv; date columns are parsed strictly as ISO dates."""
    table = pd.read_csv(path, encoding=ENCODING)
    for column in date_columns:
        table[column] = pd.to_datetime(table[column], format=DATE_FORMAT)
    return table
