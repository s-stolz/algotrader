from __future__ import annotations


class BrokerInstrumentMismatchError(ValueError):
    pass


def verify_instrument_binding(expected_symbol_id: int | None, actual_symbol_id: int) -> None:
    if expected_symbol_id is not None and expected_symbol_id != actual_symbol_id:
        raise BrokerInstrumentMismatchError(
            "Broker instrument no longer matches the stored market source "
            f"(expected {expected_symbol_id}, resolved {actual_symbol_id})"
        )
