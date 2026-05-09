from __future__ import annotations

import inspect
import re

import app as tar_app
import tar_project.exports as tar_exports


def _assert_html_tables_have_intro(text: str) -> None:
    for match in re.finditer(r'<div class="table-scroll[^"]*">\s*<table class="tar-table', text):
        previous = text[max(0, match.start() - 700):match.start()]
        last_table_end = previous.rfind("</table>")
        local_context = previous[last_table_end + len("</table>"):] if last_table_end >= 0 else previous
        assert '<p class="explain-text">' in local_context


def test_tar_dashboard_uses_numbered_table_explanations() -> None:
    client = tar_app.app.test_client()

    response = client.get("/tar?scenario=a1&sensitivity_n=100&stat_n=10")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Tabela 20 - Auditoria das 15 maiores atividades totais do tanque" in text
    assert "Tabela 21 - Janelas mínimas usadas nos cálculos" in text
    assert "Tabela 24 - Resultados calculados por data, radionuclídeo e matriz" in text
    assert "Tabela 25 - Pares calculado vs ERICA Tool" in text
    assert "Tabela 27 - Testes inferenciais das janelas mínimas" in text
    assert "Tabela 26 - Comparação com Report Level e LLD por linha completa" in text
    assert "Tabela 6 - Resumo por grupo de amostras" in text
    assert "Tabela 9 - Inferência com dados reais do TAR - Afluente contra Report Level fixo" in text
    assert "Tabela 13 - Estatística descritiva dos valores calculados e estimados" in text
    assert "Tabela 19 - Critérios mínimos para suficiência estatística" in text
    assert text.count("Leitura das colunas") >= 10
    assert 'class="column-notes"' in text
    _assert_html_tables_have_intro(text)
    style = text[text.index("<style>"):text.index("</style>")]
    assert '--report-table-font-family: "Times New Roman", Times, serif;' in style
    assert ".toc-children { margin: 8px 0 0 30px; padding-left: 0; list-style: none;" in style
    assert ".toc-number { display: inline-flex; justify-content: center; min-width: 22px; color: #1d252c;" in style
    for forbidden_font in ["Segoe UI", "Tahoma", "Arial", "Helvetica"]:
        assert forbidden_font not in style
    first_table = text.index("Tabela 20 - Auditoria das 15 maiores atividades totais do tanque")
    first_table_close = text.index("</table>", first_table)
    first_column_notes = text.index("Leitura das colunas", first_table)
    assert first_column_notes > first_table_close
    detail_caption = text.index("Detalhe inferencial - Calculado vs ERICA - Geral")
    detail_intro = text.rfind('<p class="explain-text">', 0, detail_caption)
    detail_wrapper = text.rfind('<div class="table-scroll', 0, detail_caption)
    assert detail_intro < detail_wrapper < detail_caption
    assert "Esta tabela detalha os testes inferenciais do grupo Geral" in text[detail_intro:detail_wrapper]

    for term in ["&lt; MDA", "P95", "Report Level", "LLD", "CV", "p-value"]:
        assert term in text


def test_article_beta_empirical_tables_have_pre_table_explanations() -> None:
    client = tar_app.app.test_client()

    response = client.get("/tar/artigo-beta?scenario=a1&sensitivity_n=100&stat_n=10")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Dados reais de atividade total TAR" in text
    assert "A Tabela 6 reúne somente as amostras reais do TAR - Afluente usadas na análise." in text
    assert "Tabela 7 - Estatística descritiva por radionuclídeo observado" in text
    assert "Tabela 8 - Resultados calculados por fórmula a partir das amostras reais" in text
    assert "Tabela 9 - Inferência com dados reais do TAR - Afluente contra Report Level fixo" in text
    assert "TAR - Efluente" not in text
    assert "Leitura das colunas" in text
    assert "&lt; MDA" in text
    _assert_html_tables_have_intro(text)


def test_exports_use_single_font_and_post_table_column_notes() -> None:
    docx_intro_source = inspect.getsource(tar_exports._add_docx_table_intro)
    docx_notes_source = inspect.getsource(tar_exports._add_docx_table_notes)
    pdf_source = inspect.getsource(tar_exports.build_tar_pdf_payload)
    exports_source = inspect.getsource(tar_exports)

    assert "Leitura das colunas" not in docx_intro_source
    assert "Leitura das colunas" in docx_notes_source
    assert 'font.name = "Times New Roman"' in exports_source
    for forbidden_font in ["Helvetica", "Arial", "Segoe UI", "Tahoma"]:
        assert forbidden_font not in exports_source
    assert '"Times-Bold"' in pdf_source
    assert '"Times-Roman"' in pdf_source
