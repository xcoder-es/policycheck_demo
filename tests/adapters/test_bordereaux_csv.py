from __future__ import annotations

from datetime import date
from decimal import Decimal

from policycheck_demo.adapters.outbound.csv.csv_bordereaux_reader import CsvBordereauxReader
from policycheck_demo.application.use_cases.generate_synthetic_bordereaux import (
    GenerateSyntheticBordereauxUseCase,
)
from policycheck_demo.domain.validation.models import BAARules
from policycheck_demo.domain.validation.services import validate_policy_against_baa


def test_csv_upload_with_expected_columns_parses() -> None:
    content = b"policy_number,insured_name,bind_date,territory,class_of_business,sum_insured,premium,endorsements,broker,status\nPC-1,Acme Ltd,2026-01-10,United Kingdom,Cyber,1000000,15000,Sanctions Clause,Broker,Bound\n"
    rows, errors, warnings = CsvBordereauxReader().read(content)
    assert not errors
    assert rows[0].policy_number == "PC-1"
    assert rows[0].bind_date == date(2026, 1, 10)
    assert warnings == []


def test_csv_upload_with_synonym_columns_maps() -> None:
    content = b"policy ref,client,inception_date,country,class,limit,gwp,clauses,producer,state\nREF-1,Client Ltd,2026-02-01,Ireland,Cyber,500000,9000,Sanctions Clause,A Broker,Bound\n"
    rows, errors, _warnings = CsvBordereauxReader().read(content)
    assert not errors
    assert rows[0].policy_number == "REF-1"
    assert rows[0].territory == "Ireland"
    assert rows[0].sum_insured == Decimal("500000")


def test_missing_optional_columns_handled() -> None:
    content = b"policy_number,bind_date,territory,class_of_business,sum_insured,endorsements\nPC-1,2026-01-10,United Kingdom,Cyber,1000000,Sanctions Clause\n"
    rows, errors, _warnings = CsvBordereauxReader().read(content)
    assert not errors
    assert rows[0].insured_name == "Unknown insured"


def test_missing_critical_columns_returns_friendly_warning() -> None:
    content = b"policy_number,insured_name\nPC-1,Acme Ltd\n"
    rows, errors, warnings = CsvBordereauxReader().read(content)
    assert not errors
    assert rows
    assert warnings


def test_empty_csv_handled() -> None:
    rows, errors, _warnings = CsvBordereauxReader().read(b"")
    assert rows == []
    assert errors


def test_generated_synthetic_bordereaux_has_requested_row_count() -> None:
    baa = BAARules(
        agreement_name="Test Binder",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        territories=["United Kingdom"],
        classes_of_business=["Cyber"],
        authority_limit=Decimal("1000000"),
        required_endorsements=["Sanctions Clause"],
    )
    rows = GenerateSyntheticBordereauxUseCase().execute(baa, 25)
    assert len(rows) == 25


def test_generated_synthetic_bordereaux_has_mixed_results() -> None:
    baa = BAARules(
        agreement_name="Test Binder",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        territories=["United Kingdom"],
        classes_of_business=["Cyber"],
        authority_limit=Decimal("1000000"),
        required_endorsements=["Sanctions Clause"],
    )
    rows = GenerateSyntheticBordereauxUseCase().execute(baa, 50)
    statuses = {validate_policy_against_baa(row, baa).status for row in rows}
    assert len(statuses) > 1
