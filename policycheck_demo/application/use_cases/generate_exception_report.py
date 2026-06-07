from __future__ import annotations

from policycheck_demo.domain.validation.models import ValidationResult
from policycheck_demo.ports.report_writer import ReportWriter


class GenerateExceptionReportUseCase:
    def __init__(self, writer: ReportWriter) -> None:
        self.writer = writer

    def execute(self, results: list[ValidationResult]) -> str:
        return self.writer.write_exception_report(results)
