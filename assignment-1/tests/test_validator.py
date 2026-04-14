import pytest

from src.legal_extract.schemas import OutputType
from src.legal_extract.validator import ValidationError, validate_and_normalize


def test_validate_string():
    value, notes = validate_and_normalize("  Hello   World  ", OutputType.STRING)
    assert value == "Hello World"
    assert notes == []


def test_validate_number_from_string():
    value, notes = validate_and_normalize("Rs. 27,500", OutputType.NUMBER)
    assert value == 27500
    assert notes == []


def test_validate_date_normalizes_to_iso():
    value, notes = validate_and_normalize("05/04/2026", OutputType.DATE)
    assert value in {"2026-04-05", "2026-05-04"}
    assert notes == []


def test_validate_array_of_strings():
    value, notes = validate_and_normalize([" Party A ", "Party B"], OutputType.ARRAY_STRING)
    assert value == ["Party A", "Party B"]
    assert notes == []


def test_validate_array_of_numbers():
    value, notes = validate_and_normalize(["5.25", "3,500", 7], OutputType.ARRAY_NUMBER)
    assert value == [5.25, 3500, 7]
    assert notes == []


def test_validate_array_of_dates():
    value, notes = validate_and_normalize(
        ["2024-01-01", "March 15, 2024"],
        OutputType.ARRAY_DATE,
    )
    assert value[0] == "2024-01-01"
    assert value[1] == "2024-03-15"
    assert notes == []


def test_validate_number_rejects_boolean():
    with pytest.raises(ValidationError):
        validate_and_normalize(True, OutputType.NUMBER)


def test_validate_array_number_rejects_non_list():
    with pytest.raises(ValidationError):
        validate_and_normalize("not a list", OutputType.ARRAY_NUMBER)
