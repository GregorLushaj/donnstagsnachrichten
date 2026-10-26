import pytest


def normalize_title(title: str) -> str:
    """Tiny stand-in function so the test has something to check."""
    return " ".join(title.split()).strip()


def test_normalize_title_collapses_whitespace():
    assert normalize_title("  Donnerstags   Nachrichten ") == "Donnerstags Nachrichten"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a  b", "a b"),
        ("  ", ""),
        ("already clean", "already clean"),
    ],
)
def test_normalize_title_cases(raw, expected):
    assert normalize_title(raw) == expected
