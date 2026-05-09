from __future__ import annotations

import math
import inspect

from tar_project import build_tar_summary
from tar_project import exports as tar_exports
from tar_project import model as tar_model

import app as tar_app


def _summary(stat_seed: int = 123) -> dict:
    return build_tar_summary(
        tar_app.TAR_WORKBOOK_PATH,
        "a1",
        activity_workbook_path=tar_app.TAR_ACTIVITY_WORKBOOK_PATH,
        total_activity_workbook_path=tar_app.TAR_TOTAL_ACTIVITY_WORKBOOK_PATH,
        stat_n=10,
        stat_seed=stat_seed,
    )


def test_total_activity_review_ranks_top15_by_date_and_activity() -> None:
    review = _summary()["scenario"]["total_activity_review"]

    assert len(review["top15_rows"]) == 15
    first = review["top15_rows"][0]
    assert first["date"] == "2021-04-28"
    assert first["activity_total_bq"] == 269000000000.0
    assert first["sample_id"] == "9922/2021"

    duplicated_date = review["top15_rows"][1]
    assert duplicated_date["date"] == "2023-11-20"
    assert duplicated_date["activity_total_bq"] == 207000000000.0
    assert duplicated_date["status"] == "sem composição completa"
    assert duplicated_date["numeric_count"] == 0


def test_total_activity_review_builds_minimum_windows_with_mda_as_censored() -> None:
    review = _summary()["scenario"]["total_activity_review"]

    assert [row["date"] for row in review["complete_rows"]] == ["2021-05-11", "2022-09-20", "2022-08-30"]
    assert len(review["complete_rows"]) == 3
    assert len(review["window_rows"]) == 21
    assert len(review["window_dates"]) == 21

    may_2021 = next(row for row in review["window_rows"] if row["anchor_date"] == "2021-05-11")
    assert may_2021["window_start_date"] == "2021-05-11"
    assert may_2021["window_end_date"] == "2021-05-11"
    assert may_2021["censored_radionuclides"] == ["Zr-95"]
    assert may_2021["numeric_count"] == 8
    assert may_2021["filled_count"] == 8

    nov_2023 = next(row for row in review["window_rows"] if row["anchor_date"] == "2023-11-20")
    assert nov_2023["window_start_date"] == "2023-11-20"
    assert nov_2023["window_end_date"] == "2023-12-05"
    assert nov_2023["window_span_days"] == 15


def test_total_activity_review_matrix_calculation_matches_known_row() -> None:
    review = _summary()["scenario"]["total_activity_review"]

    co58_water = next(
        row
        for row in review["matrix_rows"]
        if row["date"] == "2021-05-11"
        and row["radionuclide"] == "Co-58"
        and row["compartment_key"] == "water"
    )
    expected_sum = 64497.0
    expected_fraction = 40400.0 / expected_sum
    expected_activity = 92100000000.0 * expected_fraction
    expected_water = expected_activity / 897000000.0

    assert math.isclose(co58_water["fraction"], expected_fraction, rel_tol=1e-12)
    assert math.isclose(co58_water["activity_bq"], expected_activity, rel_tol=1e-12)
    assert math.isclose(co58_water["value"], expected_water, rel_tol=1e-12)
    assert co58_water["unit"] == "Bq/m³"


def test_generated_erica_values_are_reproducible_and_marked(monkeypatch) -> None:
    monkeypatch.setitem(tar_model.ERICA_TOOL_VALUES["Co-58"], "water", None)

    first = _summary(stat_seed=777)["scenario"]["total_activity_review"]
    second = _summary(stat_seed=777)["scenario"]["total_activity_review"]

    first_generated = [
        row
        for row in first["erica_pair_rows"]
        if row["radionuclide"] == "Co-58" and row["compartment_key"] == "water"
    ]
    second_generated = [
        row
        for row in second["erica_pair_rows"]
        if row["radionuclide"] == "Co-58" and row["compartment_key"] == "water"
    ]

    assert first_generated
    assert all(row["erica_generated"] for row in first_generated)
    assert all(row["erica_value_text"].endswith("*") for row in first_generated)
    assert [row["erica_value_text"] for row in first_generated] == [
        row["erica_value_text"] for row in second_generated
    ]
    assert any(row["generated_erica_count"] > 0 for row in first["inferential_rows"])


def test_calculated_vs_erica_inferential_tests_are_not_only_ratios() -> None:
    review = _summary()["scenario"]["total_activity_review"]

    erica_tests = [
        row
        for row in review["inferential_rows"]
        if row.get("comparison_type") == "Calculado vs ERICA"
    ]
    assert erica_tests
    assert any(row.get("group_type") == "Radionuclídeo" and row.get("scope") == "Co-58" for row in erica_tests)

    co58_water = next(
        row
        for row in erica_tests
        if row.get("group_type") == "Radionuclídeo-matriz"
        and row.get("scope") == "Co-58 - Água"
    )
    assert co58_water["n"] >= 3
    assert co58_water["test_label"] in {
        "Teste t pareado sobre log(calculado/ERICA)",
        "Wilcoxon pareado sobre log(calculado/ERICA)",
    }
    assert co58_water["p_value"] is not None
    assert co58_water["p_value_text"] != "—"
    assert "Comparação pareada" in co58_water["conclusion"]


def test_api_html_and_exports_include_total_activity_review() -> None:
    client = tar_app.app.test_client()

    payload_response = client.get("/api/tar/summary?scenario=a1&stat_n=10")
    payload = payload_response.get_json()
    review = payload["scenario"]["total_activity_review"]

    assert payload_response.status_code == 200
    assert "total_activity_workbook_path" in payload
    assert len(review["complete_rows"]) == 3
    assert len(review["window_rows"]) == 21
    chart_payloads = review["erica_chart_payloads"]
    assert [row["scope_label"] for row in chart_payloads["scope_rows"]] == [
        "Geral",
        "Água",
        "Peixe",
        "Invertebrado",
        "Sedimento",
    ]
    assert chart_payloads["scope_rows"][0]["stats"]["n"] == len(review["erica_pair_rows"])
    assert len(chart_payloads["heatmap"]["cells"]) == 32

    dashboard = client.get("/tar?scenario=a1&stat_n=10")
    dashboard_text = dashboard.get_data(as_text=True)
    assert dashboard.status_code == 200
    assert '<main class="report-pages">' in dashboard_text
    assert "@page { size: A4; margin: 1.8cm 1.6cm 1.8cm 1.8cm; }" in dashboard_text
    assert "main.report-pages { max-width: 1020px;" in dashboard_text
    assert ".tar-header, .panel { width: 210mm;" in dashboard_text
    assert "tar-table--fit" in dashboard_text
    assert "table-scroll--fit" in dashboard_text
    assert '<colgroup><col style="width:' in dashboard_text
    assert ".tar-table--fit { width: 100%; max-width: 100%; table-layout: fixed; }" in dashboard_text
    assert "overflow-wrap: anywhere" in dashboard_text
    assert ".tar-table--fit .pill" in dashboard_text
    assert "text-align: justify" in dashboard_text
    assert '<section class="panel toc-panel" id="sumario">' in dashboard_text
    assert '<span class="toc-number">2</span>Metodologia' in dashboard_text
    assert '<span class="toc-number">2.1</span>Fontes e cruzamento' in dashboard_text
    assert '<span class="toc-number">3</span>Apresentação dos dados' in dashboard_text
    assert '<span class="toc-number">4</span>Concentrações por fórmulas' in dashboard_text
    assert '<span class="toc-number">5</span>Calculado x ERICA' in dashboard_text
    assert '<span class="toc-number">6</span>Estatística descritiva' in dashboard_text
    assert '<span class="toc-number">7</span>Estatística inferencial' in dashboard_text
    assert '<span class="toc-number">8</span>Report Level e LLD' in dashboard_text
    assert 'href="#atividade-total-erica"' in dashboard_text
    assert 'href="#atividade-total-inferencia"' in dashboard_text
    assert 'href="/tar/export-report.pdf?' in dashboard_text
    assert "Gerar PDF" in dashboard_text
    assert 'Apresentação dos dados' in dashboard_text
    assert 'Cálculo das concentrações por fórmulas' in dashboard_text
    assert 'Comparação atividade calculada x ERICA Tool' in dashboard_text
    assert dashboard_text.index('id="metodologia"') < dashboard_text.index('id="atividade-total-analise-dados"')
    assert dashboard_text.index('id="atividade-total-analise-dados"') < dashboard_text.index('id="atividade-total-formulas"')
    assert dashboard_text.index('id="atividade-total-formulas"') < dashboard_text.index('id="atividade-total-erica"')
    assert dashboard_text.index('id="atividade-total-erica"') < dashboard_text.index('id="atividade-total-descritiva"')
    assert dashboard_text.index('id="atividade-total-descritiva"') < dashboard_text.index('id="atividade-total-inferencia"')
    assert dashboard_text.index('id="atividade-total-inferencia"') < dashboard_text.index('id="atividade-total-normas"')
    assert dashboard_text.index('id="atividade-total-normas"') < dashboard_text.index('id="suficiencia-estatistica"')
    assert 'data-chart="erica-boxplot"' in dashboard_text
    assert 'data-chart="erica-heatmap"' in dashboard_text
    assert "razão = 1" in dashboard_text
    assert "O boxplot resume a razão calculado/ERICA por escopo" in dashboard_text
    assert "O heatmap mostra a mediana da razão calculado/ERICA" in dashboard_text
    assert "Geral: cada ponto representa um par data/radionuclídeo/matriz" in dashboard_text
    assert "Água: cada ponto representa um par data/radionuclídeo/matriz" in dashboard_text
    assert "Peixe: cada ponto representa um par data/radionuclídeo/matriz" in dashboard_text
    assert "pontos acima indicam concentração calculada maior que ERICA" in dashboard_text
    assert "pontos abaixo indicam concentração calculada menor que ERICA" in dashboard_text
    assert "ERICA gerado por stat_seed" in dashboard_text
    assert "Nº ERICA gerado" in dashboard_text
    assert "zero não significa ERICA igual a zero" in dashboard_text
    assert "Tabela 20 - Auditoria das 15 maiores atividades totais do tanque" in dashboard_text
    assert "Tabela 21 - Janelas mínimas usadas nos cálculos" in dashboard_text
    assert "Tabela 24 - Resultados calculados por data, radionuclídeo e matriz" in dashboard_text
    assert "Tabela 27 - Testes inferenciais das janelas mínimas" in dashboard_text
    assert "Detalhes por radionuclídeo e matriz" in dashboard_text
    assert '<details class="tar-subsection" open><summary>Co-58 - Água' in dashboard_text

    article = client.get("/tar/artigo-beta?scenario=a1&stat_n=10")
    article_text = article.get_data(as_text=True)
    assert article.status_code == 200
    assert "Resultados da atividade total e composição radionuclídica" in article_text
    assert 'href="/tar/export-report.pdf?' in article_text
    assert "Gerar PDF" in article_text
    assert "Texto incorporado do Artigo TAR corrigido" not in article_text
    assert "cover-title" in article_text
    assert "Avaliação do risco radiológico ambiental" in article_text

    docx = client.get("/tar/export-report.docx?scenario=a1&stat_n=10")
    assert docx.status_code == 200
    assert docx.content_type.startswith("application/vnd.openxmlformats-officedocument")

    pdf = client.get("/tar/export-report.pdf?scenario=a1&stat_n=10")
    assert pdf.status_code == 200
    assert pdf.content_type.startswith("application/pdf")
    assert len(pdf.data) > 100000

    pdf_source = inspect.getsource(tar_exports.build_tar_pdf_payload)
    assert "leftMargin=3.0 * cm" in pdf_source
    assert "rightMargin=2.0 * cm" in pdf_source
    for title in [
        "Metodologia",
        "Apresentação dos dados",
        "Concentrações por fórmulas",
        "Calculado x ERICA",
        "Estatística descritiva",
        "Estatística inferencial",
        "Report Level e LLD",
        "Discussão e conclusão",
    ]:
        assert title in pdf_source
    assert pdf_source.index('Paragraph("Metodologia"') < pdf_source.index('Paragraph("Apresentação dos dados"')
    assert pdf_source.index('Paragraph("Calculado x ERICA"') < pdf_source.index('Paragraph("Estatística descritiva"')
    assert pdf_source.index('Paragraph("Estatística inferencial"') < pdf_source.index('Paragraph("Report Level e LLD"')
    assert "topMargin=3.0 * cm" in pdf_source
    assert "bottomMargin=2.0 * cm" in pdf_source
