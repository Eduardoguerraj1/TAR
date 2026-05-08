from __future__ import annotations

from tar_project import build_tar_summary

import app as tar_app


def test_api_includes_calculated_erica_norm_and_statistical_rows() -> None:
    summary = build_tar_summary(tar_app.TAR_WORKBOOK_PATH, "a1", stat_n=60, stat_seed=123)
    statistical = summary["scenario"]["statistical_comparison"]

    assert statistical["sample_count"] == 60
    assert statistical["seed"] == 123
    assert statistical["synthetic"] is False
    assert statistical["random_replicates_used"] is False
    assert "sem replicações aleatórias" in statistical["source_note"]
    assert statistical["calculated_rows"]
    assert statistical["erica_rows"]
    assert statistical["norm_rows"]
    assert statistical["descriptive_rows"]
    assert statistical["inferential_rows"] == []
    assert statistical["paired_comparison_rows"]


def test_statistical_comparison_is_reproducible_with_same_seed() -> None:
    first = build_tar_summary(tar_app.TAR_WORKBOOK_PATH, "a1", stat_n=60, stat_seed=4321)
    second = build_tar_summary(tar_app.TAR_WORKBOOK_PATH, "a1", stat_n=60, stat_seed=4321)

    first_stat = first["scenario"]["statistical_comparison"]
    second_stat = second["scenario"]["statistical_comparison"]

    assert first_stat["descriptive_rows"][0]["p95_text"] == second_stat["descriptive_rows"][0]["p95_text"]
    assert first_stat["paired_comparison_rows"][0]["median_ratio_text"] == second_stat["paired_comparison_rows"][0]["median_ratio_text"]
    assert first_stat["paired_comparison_rows"][0]["p_value_text"] == second_stat["paired_comparison_rows"][0]["p_value_text"]


def test_article_beta_shows_correct_statistical_framing() -> None:
    client = tar_app.app.test_client()

    response = client.get("/tar/artigo-beta?scenario=a1&stat_n=60&stat_seed=123")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "ARTIGO BETA" in text
    assert "dados calculados por fórmulas" in text
    assert "Dados simulados pelo ERICA Tool" in text
    assert "Normas: Report Level e LLD" in text
    assert "estatística descritiva" in text
    assert "estatística inferencial" in text
    assert "sem replicações aleatórias" in text
    assert "Inferência com dados reais do TAR - Afluente" in text
    assert "Análise de sensibilidade Monte Carlo" not in text
    assert "P95 simulado / Report Level" not in text


def test_flask_api_and_healthz_remain_available() -> None:
    client = tar_app.app.test_client()

    health = client.get("/healthz")
    assert health.status_code == 200

    response = client.get("/api/tar/summary?scenario=a1&stat_n=60&stat_seed=123")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["scenario"]["statistical_comparison"]["sample_count"] == 60
    assert payload["scenario"]["statistical_comparison"]["seed"] == 123
    assert payload["scenario"]["sensitivity"] == {}
    assert payload["inferential_assessment"]["sample_unit"] == "amostra real do TAR - Afluente calculada por fórmula"
