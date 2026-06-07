from __future__ import annotations


def test_app_imports() -> None:
    from policycheck_demo.app import app

    assert app.title == "FastAPI"


def test_core_routes_exist() -> None:
    from policycheck_demo.app import app

    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/extract-baa" in paths
    assert "/process" in paths
    assert "/generate-bordereaux" in paths
    assert "/upload-bordereaux" in paths
    assert "/download-report" in paths


def test_container_wires_use_cases() -> None:
    from policycheck_demo.infrastructure.container import container

    assert container.extract_baa_rules
    assert container.validate_bordereaux
    assert container.generate_exception_report
