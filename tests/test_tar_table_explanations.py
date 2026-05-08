from __future__ import annotations

import app as tar_app


def test_tar_dashboard_uses_numbered_table_explanations() -> None:
    client = tar_app.app.test_client()

    response = client.get("/tar?scenario=a1&sensitivity_n=100&stat_n=10")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Tabela 1 - Referências normativas disponíveis por compartimento" in text
    assert "Tabela 2 - Concentrações calculadas por radionuclídeo e compartimento" in text
    assert "Tabela 3 - Comparação das concentrações com Report Level e LLD" in text
    assert "Tabela 6 - Resumo por grupo de amostras" in text
    assert "Tabela 12 - Estatística descritiva das replicações sintéticas exploratórias" in text
    assert "Tabela 18 - Critérios mínimos para suficiência estatística" in text
    assert text.count("Leitura das colunas") >= 10
    assert 'class="column-notes"' in text

    for term in ["&lt; MDA", "P95", "Report Level", "LLD", "CV", "p-value"]:
        assert term in text


def test_article_beta_empirical_tables_have_pre_table_explanations() -> None:
    client = tar_app.app.test_client()

    response = client.get("/tar/artigo-beta?scenario=a1&sensitivity_n=100&stat_n=10")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Dados reais de atividade total TAR" in text
    assert "A Tabela 6 separa as amostras reais em TAR - Afluente e TAR - Efluente." in text
    assert "Tabela 7 - Estatística descritiva por radionuclídeo observado" in text
    assert "Tabela 8 - Resultados calculados por fórmula a partir das amostras reais" in text
    assert "Leitura das colunas" in text
    assert "&lt; MDA" in text
