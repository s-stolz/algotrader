"""Organizational experiment names, independent of execution snapshots."""


def normalize_experiment_name(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.strip():
        return None
    if any(character in value for character in "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"):
        raise ValueError("Experiment name must be single-line")
    name = value.strip()
    if len(name) > 120:
        raise ValueError("Experiment name must have at most 120 characters")
    return name or None
