from __future__ import annotations

import re
from typing import Any, List, Tuple, Union
from dateutil import parser as date_parser
from .schemas import OutputType


class ValidationError(Exception):
    pass


def _clean_string(value: Any) -> str:
    if value is None:
        raise ValidationError("Value is None")

    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        raise ValidationError("String value is empty after cleanup")

    return text


def _parse_number(value: Any) -> Union[int, float]:
    if value is None:
        raise ValidationError("Value is None")

    if isinstance(value, bool):
        raise ValidationError("Boolean is not a valid number")

    if isinstance(value, (int, float)):
        return value

    text = _clean_string(value)
    text = text.replace(",", "")

    matches = re.findall(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9])", text)
    if not matches:
        raise ValidationError(f"Could not extract numeric value from: {value}")

    num_str = matches[0]
    if "." in num_str:
        return float(num_str)
    return int(num_str)


def _normalize_date_text(text: str) -> str:
    text = _clean_string(text)

    # 13thAug2024 -> 13Aug2024
    # 13th Aug 2024 -> 13 Aug 2024
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text, flags=re.IGNORECASE)

    # 13Aug2024 -> 13 Aug2024
    text = re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)

    # Aug2024 -> Aug 2024
    text = re.sub(r"([A-Za-z])(\d)", r"\1 \2", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(value: Any) -> str:
    if value is None:
        raise ValidationError("Value is None")

    text = _normalize_date_text(str(value))

    try:
        dt = date_parser.parse(text, dayfirst=True, fuzzy=True)
    except Exception as e:
        raise ValidationError(f"Could not parse date from '{value}': {e}") from e

    return dt.date().isoformat()


def _validate_scalar(value: Any, output_type: OutputType) -> Union[str, int, float]:
    if output_type == OutputType.STRING:
        return _clean_string(value)

    if output_type == OutputType.NUMBER:
        return _parse_number(value)

    if output_type == OutputType.DATE:
        return _parse_date(value)

    raise ValidationError(f"Unsupported scalar output type: {output_type}")


def validate_and_normalize(value: Any, output_type: OutputType) -> Tuple[Any, List[str]]:
    notes: List[str] = []

    if output_type in {OutputType.STRING, OutputType.NUMBER, OutputType.DATE}:
        normalized = _validate_scalar(value, output_type)
        return normalized, notes

    if output_type == OutputType.ARRAY_STRING:
        if not isinstance(value, list):
            raise ValidationError("Expected array/list value")
        return [_clean_string(item) for item in value], notes

    if output_type == OutputType.ARRAY_NUMBER:
        if not isinstance(value, list):
            raise ValidationError("Expected array/list value")
        return [_parse_number(item) for item in value], notes

    if output_type == OutputType.ARRAY_DATE:
        if not isinstance(value, list):
            raise ValidationError("Expected array/list value")
        return [_parse_date(item) for item in value], notes

    raise ValidationError(f"Unsupported output type: {output_type}")