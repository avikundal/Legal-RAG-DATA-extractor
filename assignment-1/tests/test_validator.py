from src.legal_extract.schemas import OutputType
from src.legal_extract.validator import validate_and_normalize


def test_validate_string():
    value, _ = validate_and_normalize("  Avijit   Kundal  ", OutputType.STRING)
    assert value == "Avijit Kundal"


def test_validate_number():
    value, _ = validate_and_normalize("Rs.4000/- per hour", OutputType.NUMBER)
    assert value == 4000


def test_validate_date():
    value, _ = validate_and_normalize("12 DEC 2025", OutputType.DATE)
    assert value == "2025-12-12"


def test_validate_array_date():
    value, _ = validate_and_normalize(["12/12/2025", "2025-12-13"], OutputType.ARRAY_DATE)
    assert value == ["2025-12-12", "2025-12-13"]
