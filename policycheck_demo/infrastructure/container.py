from __future__ import annotations

from dataclasses import dataclass

from policycheck_demo.adapters.outbound.ai.fallback_rule_extractor import FallbackRuleExtractor
from policycheck_demo.adapters.outbound.ai.huggingface_summary_generator import HuggingFaceSummaryGenerator
from policycheck_demo.adapters.outbound.csv.csv_bordereaux_reader import CsvBordereauxReader
from policycheck_demo.adapters.outbound.csv.csv_exception_report_writer import CsvExceptionReportWriter
from policycheck_demo.adapters.outbound.pdf.pypdf_text_extractor import PyPdfTextExtractor
from policycheck_demo.application.use_cases.extract_baa_rules import ExtractBAARulesUseCase
from policycheck_demo.application.use_cases.generate_exception_report import GenerateExceptionReportUseCase
from policycheck_demo.application.use_cases.generate_synthetic_bordereaux import (
    GenerateSyntheticBordereauxUseCase,
)
from policycheck_demo.application.use_cases.validate_bordereaux import ValidateBordereauxUseCase
from policycheck_demo.application.use_cases.validate_single_policy import ValidateSinglePolicyUseCase
from policycheck_demo.infrastructure.config import AppConfig, load_config


@dataclass
class AppContainer:
    config: AppConfig
    pdf_text_extractor: PyPdfTextExtractor
    rule_extractor: FallbackRuleExtractor
    summary_generator: HuggingFaceSummaryGenerator
    bordereaux_reader: CsvBordereauxReader
    report_writer: CsvExceptionReportWriter
    extract_baa_rules: ExtractBAARulesUseCase
    validate_single_policy: ValidateSinglePolicyUseCase
    generate_synthetic_bordereaux: GenerateSyntheticBordereauxUseCase
    validate_bordereaux: ValidateBordereauxUseCase
    generate_exception_report: GenerateExceptionReportUseCase


def build_container() -> AppContainer:
    config = load_config()
    pdf_extractor = PyPdfTextExtractor()
    rule_extractor = FallbackRuleExtractor()
    summary_generator = HuggingFaceSummaryGenerator()
    bordereaux_reader = CsvBordereauxReader()
    report_writer = CsvExceptionReportWriter()
    return AppContainer(
        config=config,
        pdf_text_extractor=pdf_extractor,
        rule_extractor=rule_extractor,
        summary_generator=summary_generator,
        bordereaux_reader=bordereaux_reader,
        report_writer=report_writer,
        extract_baa_rules=ExtractBAARulesUseCase(pdf_extractor, rule_extractor),
        validate_single_policy=ValidateSinglePolicyUseCase(),
        generate_synthetic_bordereaux=GenerateSyntheticBordereauxUseCase(),
        validate_bordereaux=ValidateBordereauxUseCase(summary_generator),
        generate_exception_report=GenerateExceptionReportUseCase(report_writer),
    )


container = build_container()
