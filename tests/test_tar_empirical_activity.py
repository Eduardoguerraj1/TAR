from __future__ import annotations

from tar_project import build_tar_summary

import app as tar_app


def _summary() -> dict:
    return build_tar_summary(
        tar_app.TAR_WORKBOOK_PATH,
        "a1",
        activity_workbook_path=tar_app.TAR_ACTIVITY_WORKBOOK_PATH,
        sensitivity_n=100,
        stat_n=10,
        stat_seed=123,
    )


def test_empirical_activity_statistics_reads_real_xls_by_group() -> None:
    empirical = _summary()["scenario"]["empirical_activity_statistics"]

    assert empirical["synthetic"] is False
    assert empirical["group_counts"]["TAR - Afluente"] == 301
    assert empirical["group_counts"]["TAR - Efluente"] == 20
    assert "Nb-95" in empirical["observed_radionuclides"]
    assert empirical["unmodeled_radionuclides"] == ["Nb-95"]
    assert "< MDA>" in empirical["mda_policy"]

    cr51_rows = [row for row in empirical["radionuclide_rows"] if row["radionuclide"] == "Cr-51"]
    assert cr51_rows
    assert sum(row["censored_count"] for row in cr51_rows) == 198


def test_empirical_activity_applies_tar_formula_to_modeled_compartments() -> None:
    empirical = _summary()["scenario"]["empirical_activity_statistics"]

    modeled_rows = empirical["modeled_compartment_rows"]
    assert modeled_rows
    assert not any(row["radionuclide"] == "Nb-95" for row in modeled_rows)

    co58_water = next(
        row
        for row in modeled_rows
        if row["group"] == "TAR - Afluente"
        and row["radionuclide"] == "Co-58"
        and row["compartment_key"] == "water"
    )
    assert co58_water["n"] > 0
    assert co58_water["p95"] is not None
    assert co58_water["report_level"] == 37000.0
    assert co58_water["lld"] == 560.0
    assert co58_water["report_level_status"] in {"abaixo", "acima"}


def test_api_and_article_beta_include_empirical_activity_section() -> None:
    client = tar_app.app.test_client()

    health = client.get("/healthz")
    assert health.status_code == 200
    assert "activity_workbook_path" in health.get_json()

    response = client.get("/api/tar/summary?scenario=a1&sensitivity_n=100&stat_n=10")
    payload = response.get_json()
    empirical = payload["scenario"]["empirical_activity_statistics"]
    assert response.status_code == 200
    assert empirical["synthetic"] is False
    assert empirical["group_counts"]["TAR - Afluente"] == 301
    assert empirical["group_counts"]["TAR - Efluente"] == 20

    article = client.get("/tar/artigo-beta?scenario=a1&sensitivity_n=100&stat_n=10")
    text = article.get_data(as_text=True)
    assert article.status_code == 200
    assert "Dados reais de atividade total TAR" in text
    assert "TAR - Afluente" in text
    assert "TAR - Efluente" in text
    assert "&lt; MDA" in text


def test_docx_and_pdf_exports_include_empirical_activity_section() -> None:
    client = tar_app.app.test_client()

    docx = client.get("/tar/export-report.docx?scenario=a1&sensitivity_n=100&stat_n=10")
    assert docx.status_code == 200
    assert docx.content_type.startswith("application/vnd.openxmlformats-officedocument")

    pdf = client.get("/tar/export-report.pdf?scenario=a1&sensitivity_n=100&stat_n=10")
    assert pdf.status_code == 200
    assert pdf.content_type.startswith("application/pdf")
