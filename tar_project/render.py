from __future__ import annotations

import math
import re
from html import escape, unescape
from pathlib import Path
from typing import Any

from .model import COMPARTMENTS, INFERENTIAL_TEST_MINIMUMS, SCENARIOS
from .table_meta import tar_table_meta


REPORT_FULL_TITLE = (
    "Avaliação do risco radiológico ambiental em ambiente marinho e seus compartimentos "
    "a partir de uma liberação não planejada em uma usina nuclear do tipo PWR"
)


def _text(value: Any) -> str:
    return escape(str(value or ""))


def _format_number(value: Any, *, digits: int = 3) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{numeric:.{digits}f}".replace(".", ",")


def _format_sci(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{numeric:.2E}".replace("E+0", "E+").replace("E-0", "E-")


def _status_class(status: str) -> str:
    if status == "acima":
        return "bad"
    if status == "abaixo":
        return "good"
    return "muted"


def _scenario_tabs(selected_scenario: str, *, report: bool = False, base_path: str | None = None) -> str:
    base_path = base_path or ("/tar/report-preview" if report else "/tar")
    links = []
    for key, spec in SCENARIOS.items():
        selected = " selected" if key == selected_scenario else ""
        links.append(f'<a class="scenario-tab{selected}" href="{base_path}?scenario={key}">{escape(spec["label"])}</a>')
    return "".join(links)


def _scenario_query_suffix(summary: dict[str, Any]) -> str:
    scenario = summary.get("scenario") or {}
    sensitivity = scenario.get("sensitivity") or {}
    statistical = scenario.get("statistical_comparison") or {}
    sensitivity_suffix = (
        f"&sensitivity_n={escape(str(sensitivity.get('sample_count') or 10000))}"
        f"&sensitivity_seed={escape(str(sensitivity.get('seed') or 20260504))}"
    )
    stat_suffix = (
        f"&stat_n={escape(str(statistical.get('sample_count') or 60))}"
        f"&stat_seed={escape(str(statistical.get('seed') or 20260504))}"
    )
    if not scenario.get("is_hypothetical"):
        return f"scenario={escape(str(summary['selected_scenario']))}{sensitivity_suffix}{stat_suffix}"
    return (
        f"scenario={escape(str(summary['selected_scenario']))}"
        f"&n={escape(str(scenario.get('measurement_count') or 60))}"
        f"&seed={escape(str(scenario.get('seed') or 20260504))}"
        f"{sensitivity_suffix}"
        f"{stat_suffix}"
    )


def _explain_text(text: str) -> str:
    return f'<p class="explain-text">{escape(text)}</p>' if text else ""


def _column_notes_html(notes: list[str]) -> str:
    if not notes:
        return ""
    items = "".join(f"<li>{escape(note)}</li>" for note in notes)
    return f'<div class="column-notes-block"><strong>Leitura das colunas</strong><ol class="column-notes">{items}</ol></div>'


def _table_intro_text(caption: str, intro: str) -> str:
    if intro:
        return intro
    clean_caption = " ".join((caption or "tabela").split())
    return (
        f"A tabela {clean_caption} apresenta os registros correspondentes a este bloco do relatório. "
        "A leitura deve considerar o título, as unidades indicadas e as notas de coluna apresentadas após a tabela."
    )


def _table_column_count(header_html: str) -> int:
    first_row = re.search(r"<tr\b[^>]*>(.*?)</tr>", header_html, flags=re.IGNORECASE | re.DOTALL)
    target = first_row.group(1) if first_row else header_html
    return len(re.findall(r"<th\b", target, flags=re.IGNORECASE))


def _table_first_row(html: str) -> str:
    first_row = re.search(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    return first_row.group(1) if first_row else html


def _table_cell_text(cell_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", cell_html, flags=re.IGNORECASE | re.DOTALL)
    return " ".join(unescape(text).split())


def _table_row_cells(row_html: str, tag: str) -> list[str]:
    return [
        _table_cell_text(match)
        for match in re.findall(fr"<{tag}\b[^>]*>(.*?)</{tag}>", row_html, flags=re.IGNORECASE | re.DOTALL)
    ]


def _short_numeric_column(values: list[str]) -> bool:
    filled = [value.strip() for value in values if value.strip() and value.strip() != "—"]
    if not filled:
        return False
    return all(re.fullmatch(r"[+-]?\d", value) for value in filled)


def _table_colgroup_html(header_html: str, body_html: str, column_count: int) -> str:
    if column_count <= 0:
        return ""
    headers = _table_row_cells(_table_first_row(header_html), "th")
    body_columns: list[list[str]] = [[] for _ in range(column_count)]
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body_html, flags=re.IGNORECASE | re.DOTALL):
        cells = _table_row_cells(row_html, "td")
        for index in range(min(column_count, len(cells))):
            body_columns[index].append(cells[index])

    weights: list[float] = []
    for index in range(column_count):
        header = headers[index] if index < len(headers) else ""
        values = body_columns[index] if index < len(body_columns) else []
        header_word = max((len(word) for word in re.findall(r"\S+", header)), default=len(header))
        max_cell = max((len(value) for value in values), default=0)
        lowered = f"{header} {' '.join(values[:6])}".lower()
        if _short_numeric_column(values):
            weight = max(0.64, min(0.92, header_word * 0.08))
        elif "status" in lowered or "referência" in lowered or "composi" in lowered:
            weight = 1.55
        else:
            weight = max(0.82, min(1.55, (max(header_word, 5) * 0.08) + (min(max_cell, 18) * 0.055)))
        weights.append(weight)

    total = sum(weights) or 1.0
    columns = "".join(f'<col style="width: {(weight / total) * 100:.2f}%">' for weight in weights)
    return f"<colgroup>{columns}</colgroup>"


def _tar_table(
    class_name: str,
    caption: str,
    header_html: str,
    body_html: str,
    note: str = "",
    intro: str = "",
    *,
    table_key: str = "",
    source_note: str = "",
    unit_note: str = "",
) -> str:
    column_notes: list[str] = []
    if table_key:
        meta = tar_table_meta(table_key)
        caption = meta["display_caption"]
        intro = meta["lead_text"]
        column_notes = meta["column_notes"]
        unit_note = unit_note or meta.get("unit_note") or ""
        source_note = source_note or meta.get("source_note") or ""
    note_parts = [part for part in [unit_note, note, source_note] if part]
    note_html = "".join(f'<p class="table-note">{escape(part)}</p>' for part in note_parts)
    legend_html = "".join(part for part in [note_html, _column_notes_html(column_notes)] if part)
    if legend_html:
        legend_html = f'<div class="table-legend">{legend_html}</div>'
    column_count = _table_column_count(header_html)
    class_parts = class_name.split()
    fit_table = column_count >= 8
    if column_count >= 8 and "tar-table--wide" not in class_parts:
        class_parts.append("tar-table--wide")
    if fit_table and "tar-table--fit" not in class_parts:
        class_parts.append("tar-table--fit")
    resolved_class_name = " ".join(class_parts)
    scroll_class = "table-scroll table-scroll--fit" if fit_table else "table-scroll"
    colgroup_html = _table_colgroup_html(header_html, body_html, column_count) if fit_table else ""
    return (
        f"{_explain_text(_table_intro_text(caption, intro))}"
        f'<div class="{scroll_class}">'
        f'<table class="tar-table {resolved_class_name}">'
        f"<caption>{escape(caption)}</caption>"
        f"{colgroup_html}"
        f"<thead>{header_html}</thead>"
        f"<tbody>{body_html}</tbody></table>"
        f"</div>"
        f"{legend_html}"
    )


def _safe_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:
        return None
    return numeric


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        numeric = _safe_float(row.get(key))
        if numeric is not None:
            values.append(numeric)
    return values


def _min_max_text(values: list[float]) -> str:
    if not values:
        return "—"
    return f"{_format_sci(min(values))} a {_format_sci(max(values))}"


def _mean_text(values: list[float]) -> str:
    if not values:
        return "—"
    return _format_sci(sum(values) / len(values))


def _compartment_sort_key(compartment_key: str) -> int:
    for index, compartment in enumerate(COMPARTMENTS):
        if compartment.get("key") == compartment_key:
            return index
    return len(COMPARTMENTS)


def _group_by_radionuclide_matrix(
    rows: list[dict[str, Any]],
) -> list[tuple[tuple[str, str, str], list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        radionuclide = str(row.get("radionuclide") or "—")
        compartment_key = str(row.get("compartment_key") or "")
        compartment = str(row.get("compartment") or "—")
        grouped.setdefault((radionuclide, compartment_key, compartment), []).append(row)
    return sorted(grouped.items(), key=lambda item: (item[0][0], _compartment_sort_key(item[0][1]), item[0][2]))


def _distinct_count(rows: list[dict[str, Any]], key: str) -> int:
    return len({str(row.get(key) or "") for row in rows if row.get(key)})


def _details_section(title: str, content: str, *, open_by_default: bool = False) -> str:
    open_attr = " open" if open_by_default else ""
    return f'<details class="tar-subsection"{open_attr}><summary>{escape(title)}</summary>{content}</details>'


def _report_toc(items: list[dict[str, Any]]) -> str:
    rows = []
    for index, item in enumerate(items, start=1):
        item_number = str(item.get("number") or index)
        children_html = ""
        children = item.get("children") or []
        if children:
            child_rows = []
            for child_index, child in enumerate(children, start=1):
                child_number = str(child.get("number") or f"{item_number}.{child_index}")
                child_rows.append(
                    "<li>"
                    f'<a href="#{escape(str(child.get("id") or ""))}"><span class="toc-number">{escape(child_number)}</span>{escape(str(child.get("title") or ""))}</a>'
                    f'<span>{escape(str(child.get("description") or ""))}</span>'
                    "</li>"
                )
            children_html = f'<ol class="toc-children">{"".join(child_rows)}</ol>'
        rows.append(
            "<li>"
            f'<a class="toc-title" href="#{escape(str(item.get("id") or ""))}">'
            f'<span class="toc-number">{escape(item_number)}</span>{escape(str(item.get("title") or ""))}</a>'
            f'<p>{escape(str(item.get("description") or ""))}</p>'
            f"{children_html}</li>"
        )
    return f"""
<section class="panel toc-panel" id="sumario">
  <h2>Sumário</h2>
  <p>Roteiro detalhado do relatório, separando dados, metodologia, cálculos, ERICA Tool, normas e inferência estatística.</p>
  <ol class="toc-list">{''.join(rows)}</ol>
</section>
"""


def _toc_item(
    item_id: str,
    title: str,
    description: str,
    children: list[dict[str, str]] | None = None,
    *,
    number: str = "",
) -> dict[str, Any]:
    item = {"id": item_id, "title": title, "description": description, "children": children or []}
    if number:
        item["number"] = number
    return item


def _toc_child(item_id: str, title: str, description: str, *, number: str = "") -> dict[str, str]:
    item = {"id": item_id, "title": title, "description": description}
    if number:
        item["number"] = number
    return item


def _reference_counts_table(summary: dict[str, Any]) -> str:
    scenario = summary["scenario"]
    rows = []
    for compartment in COMPARTMENTS:
        count = scenario["reference_counts"][compartment["key"]]
        rows.append(
            "<tr>"
            f"<td>{escape(count['label'])}</td>"
            f"<td>{count['report_level']}</td>"
            f"<td>{count['lld']}</td>"
            f"<td>{escape(', '.join(count['report_level_radionuclides']) or 'sem referência')}</td>"
            "</tr>"
        )
    return _tar_table(
        "",
        "Referências normativas disponíveis por compartimento",
        "<tr><th>Compartimento</th><th>Report Level</th><th>LLD</th><th>Radionuclídeos com referência</th></tr>",
        "".join(rows),
        "Report Level é o critério de notificação usado na comparação; LLD é referência de detecção e não limite de ação.",
        "Esta tabela identifica onde há referência numérica cadastrada para comparar os resultados do TAR. Ela ajuda a separar compartimentos avaliáveis daqueles classificados como sem referência.",
        table_key="reference_counts",
    )


def _concentration_table(summary: dict[str, Any]) -> str:
    rows = []
    for item in summary["scenario"]["rows"]:
        cells = [f"<td>{escape(item['radionuclide'])}</td>"]
        for compartment in COMPARTMENTS:
            data = item["compartments"][compartment["key"]]
            cells.append(f"<td>{escape(data['value_text'])}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    statistic_label = "P95 simulado" if summary["scenario"].get("is_hypothetical") else "Concentração"
    headers = "".join(f"<th>{escape(comp['label'])}<span>{escape(comp['unit'])} · {statistic_label}</span></th>" for comp in COMPARTMENTS)
    note = (
        "P95 representa o percentil 95 das simulações do cenário hipotético."
        if summary["scenario"].get("is_hypothetical")
        else "Os valores são resultados calculados do modelo determinístico; n corresponde aos radionuclídeos, não a amostras independentes."
    )
    return _tar_table(
        "tar-table--dense",
        "Concentrações calculadas por radionuclídeo e compartimento",
        f"<tr><th>Radionuclídeo</th>{headers}</tr>",
        "".join(rows),
        note,
        "Esta tabela resume os valores calculados por radionuclídeo em cada compartimento ambiental. No cenário hipotético, o valor mostrado é o P95 das simulações; nos cenários reais, é o resultado determinístico da planilha.",
        table_key="concentrations",
    )


def _reference_result_table(summary: dict[str, Any]) -> str:
    rows = []
    for item in summary["scenario"]["rows"]:
        for compartment in COMPARTMENTS:
            data = item["compartments"][compartment["key"]]
            rows.append(
                "<tr>"
                f"<td>{escape(item['radionuclide'])}</td>"
                f"<td>{escape(compartment['label'])}</td>"
                f"<td>{escape(data['value_text'])}</td>"
                f"<td>{escape(data['report_level_text'])}</td>"
                f"<td>{escape(data['report_level_ratio_text'])}</td>"
                f'<td><span class="pill {_status_class(data["report_level_status"])}">{escape(data["report_level_status"])}</span></td>'
                f"<td>{escape(data['lld_text'])}</td>"
                f"<td>{escape(data['lld_ratio_text'])}</td>"
                f'<td><span class="pill {_status_class(data["lld_status"])}">{escape(data["lld_status"])}</span></td>'
                "</tr>"
            )
    return _tar_table(
        "tar-table--dense",
        "Comparação das concentrações com Report Level e LLD",
        "<tr><th>Radionuclídeo</th><th>Compartimento</th><th>Concentração</th>"
        "<th>Report Level</th><th>Razão valor/Report Level</th><th>Status Report Level</th>"
        "<th>LLD</th><th>Razão valor/LLD</th><th>Status LLD</th></tr>",
        "".join(rows),
        "Report Level indica o nível de notificação cadastrado; LLD indica referência de detecção. Status 'sem referência' significa ausência de valor cadastrado para o compartimento.",
        "Esta tabela compara cada concentração com o Report Level e o LLD disponíveis. A razão mostra quantas vezes o valor calculado representa em relação à referência; valores acima de 1 indicam superação da referência correspondente.",
        table_key="reference_results",
    )


def _minimums_table() -> str:
    rows = []
    for item in INFERENTIAL_TEST_MINIMUMS:
        rows.append(
            "<tr>"
            f"<td>{escape(item['test'])}</td>"
            f"<td>{escape(item['technical_minimum'])}</td>"
            f"<td>{escape(item['recommended'])}</td>"
            "</tr>"
        )
    return _tar_table(
        "",
        "Critérios mínimos para suficiência estatística",
        "<tr><th>Teste</th><th>Mínimo técnico</th><th>Recomendado para relatório</th></tr>",
        "".join(rows),
        "Nos cenários reais atuais, o n = 8 representa radionuclídeos calculados e não medições ambientais independentes.",
        "Esta tabela mostra os mínimos práticos para aplicar testes estatísticos com sentido técnico. Ela justifica por que a planilha consolidada atual permanece descritiva quando não há medições independentes.",
        table_key="minimums",
    )


def _hypothetical_measurements_table(summary: dict[str, Any]) -> str:
    if not summary["scenario"].get("is_hypothetical"):
        return ""
    rows = []
    for item in summary["scenario"]["rows"]:
        measurement = item["measurement_summary"]
        rows.append(
            "<tr>"
            f"<td>{escape(item['radionuclide'])}</td>"
            f"<td>{item['measurement_count']}</td>"
            f"<td>{escape(item['source_concentration_bq_m3_text'])}</td>"
            f"<td>{escape(measurement['mean_text'])}</td>"
            f"<td>{escape(measurement['median_text'])}</td>"
            f"<td>{escape(measurement['p95_text'])}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Resumo das medições sintéticas da água do TAR",
        "<tr><th>Radionuclídeo</th><th>n</th><th>Valor base TAR (Bq/m³)</th><th>Média medida (Bq/m³)</th><th>Mediana medida (Bq/m³)</th><th>P95 medido (Bq/m³)</th></tr>",
        "".join(rows),
        "n é o número de medições sintéticas por radionuclídeo; P95 é o percentil 95 dessas medições.",
        "Esta tabela descreve as medições sintéticas geradas para a água do TAR antes de elas alimentarem as simulações ambientais. Ela permite verificar a escala da entrada simulada por radionuclídeo.",
        table_key="hypothetical_measurements",
    )


def _hypothetical_tests_table(summary: dict[str, Any]) -> str:
    if not summary["scenario"].get("is_hypothetical"):
        return ""
    rows = []
    for result in summary["scenario"].get("statistical_tests", []):
        rows.append(
            "<tr>"
            f"<td>{escape(result['radionuclide'])}</td>"
            f"<td>{escape(result['compartment'])}</td>"
            f"<td>{escape(str(result.get('n') or '—'))}</td>"
            f"<td>{escape(result.get('shapiro_p_text') or '—')}</td>"
            f"<td>{escape(result.get('test_label') or '—')}</td>"
            f"<td>{escape(result.get('p_value_text') or '—')}</td>"
            f"<td>{escape(result.get('p95_ratio_text') or '—')}</td>"
            f"<td>{escape(str(result.get('exceedance_count') or 0))}</td>"
            f"<td>{escape(result.get('conclusion') or '')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Teste estatístico das simulações contra o Report Level",
        "<tr><th>Radionuclídeo</th><th>Compartimento</th><th>n sim.</th><th>Shapiro-Wilk</th><th>Teste usado</th><th>p-value</th><th>P95 simulado / Report Level</th><th>Acima do limite</th><th>Conclusão</th></tr>",
        "".join(rows),
        "O teste usa o logaritmo da razão entre valor simulado e Report Level; a hipótese alternativa avalia se os resultados simulados permanecem abaixo do Report Level.",
        "Esta tabela mostra, para cada radionuclídeo e compartimento com Report Level, qual teste foi selecionado e se as simulações sustentam margem estatística abaixo da referência.",
        table_key="hypothetical_tests",
    )


def _hypothetical_panel(summary: dict[str, Any]) -> str:
    scenario = summary["scenario"]
    if not scenario.get("is_hypothetical"):
        return ""
    return f"""
<section class="panel report-block" id="hipotetico-medicoes">
  <h2>Medições sintéticas da água do TAR</h2>
  <p>O cenário hipotético parte dos valores medidos de entrada da planilha e gera {scenario['measurement_count']} medições sintéticas por radionuclídeo, com seed {scenario['seed']}. Esses valores representam uma série simulada de resultados de espectrometria gama da água do TAR e alimentam novas simulações dos compartimentos ambientais.</p>
  {_hypothetical_measurements_table(summary)}
</section>
<section class="panel report-block" id="hipotetico-inferencia">
  <h2>Teste estatístico do cenário hipotético</h2>
  <p>{escape(scenario.get('statistical_text') or '')}</p>
  {_hypothetical_tests_table(summary)}
</section>
"""


def _reference_svg(summary: dict[str, Any]) -> str:
    counts = [summary["scenario"]["reference_counts"][comp["key"]] for comp in COMPARTMENTS]
    max_value = max([count["report_level"] for count in counts] + [1])
    bar_width = 64
    gap = 38
    height = 170
    width = 80 + len(counts) * (bar_width + gap)
    bars = []
    labels = []
    for index, count in enumerate(counts):
        x = 52 + index * (bar_width + gap)
        value = count["report_level"]
        bar_height = 0 if max_value <= 0 else round((value / max_value) * 105)
        y = 126 - bar_height
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="4" fill="#27667b"/>')
        bars.append(f'<text x="{x + bar_width / 2}" y="{y - 8}" text-anchor="middle" font-size="12" fill="#18343d">{value}</text>')
        labels.append(f'<text x="{x + bar_width / 2}" y="150" text-anchor="middle" font-size="11" fill="#516873">{escape(count["label"])}</text>')
    return (
        f'<svg class="tar-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Referências disponíveis por compartimento">'
        '<line x1="40" y1="126" x2="455" y2="126" stroke="#c9d7dc"/>'
        f"{''.join(bars)}{''.join(labels)}</svg>"
    )


def _sensitivity_cards(sensitivity: dict[str, Any]) -> str:
    cards = sensitivity.get("cards") or []
    return "".join(
        f'<div class="card"><span>{escape(str(card.get("label") or ""))}</span><strong>{escape(str(card.get("value") or "—"))}</strong></div>'
        for card in cards
    )


def _sensitivity_distribution_explanation() -> str:
    return (
        '<div class="explain-box">'
        "<p>Antes da tabela, a ideia central é simples: cada rodada do Monte Carlo sorteia um valor possível para cada variável incerta e recalcula os resultados. Como ainda não foram cadastrados valores de literatura, os intervalos abaixo são sintéticos e servem para mostrar a sensibilidade do modelo.</p>"
        "<p><strong>Distribuição triangular</strong> é usada quando temos um valor mínimo, um valor mais provável e um valor máximo. Ela concentra mais sorteios perto do valor provável. Exemplo: a atividade total do TAR varia entre 0,50x e 1,00x, com 0,75x como valor mais provável.</p>"
        "<p><strong>Distribuição lognormal</strong> é usada para fatores sempre positivos que variam por multiplicação e podem crescer bastante, mas nunca ficam negativos. É adequada para bioacumulação e transferência para sedimento, porque esses fatores costumam variar por ordens de grandeza.</p>"
        "<p><strong>Distribuição uniforme</strong> é usada quando só há um intervalo inferior e superior, sem preferência por um valor central. Aqui ela representa o tempo de exposição entre 0,50x e 1,50x.</p>"
        "</div>"
    )


def _sensitivity_variables_table(sensitivity: dict[str, Any]) -> str:
    rows = []
    for variable in sensitivity.get("variables") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(variable.get('label') or '')}</td>"
            f"<td>{escape(variable.get('distribution') or '')}</td>"
            f"<td>{escape(variable.get('parameters') or '')}</td>"
            f"<td>{escape(variable.get('base_value_text') or '—')}</td>"
            f"<td>{escape(variable.get('unit') or '')}</td>"
            f"<td>{escape(variable.get('description') or '')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Distribuições sintéticas usadas no Monte Carlo",
        "<tr><th>Variável</th><th>Distribuição</th><th>Parâmetros</th><th>Base</th><th>Unidade</th><th>Uso no modelo</th></tr>",
        "".join(rows),
        sensitivity.get("source_note") or "",
        "Esta tabela documenta as escolhas usadas no sorteio: qual variável é incerta, qual distribuição foi aplicada, quais parâmetros foram usados e qual valor base do cenário serve como referência.",
        table_key="sensitivity_variables",
    )


def _sensitivity_influence_table(sensitivity: dict[str, Any]) -> str:
    rows = []
    for item in sensitivity.get("influence_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('label') or '')}</td>"
            f"<td>{escape(item.get('correlation_text') or '—')}</td>"
            f"<td>{escape(item.get('absolute_correlation_text') or '—')}</td>"
            f"<td>{escape(item.get('direction') or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Ranking de influência sobre a maior razão valor simulado / Report Level",
        "<tr><th>Variável</th><th>Correlação de Spearman</th><th>|Correlação|</th><th>Sentido</th></tr>",
        "".join(rows),
        "Correlação positiva indica que valores maiores da variável tendem a aumentar a maior razão contra o Report Level; correlação negativa indica que valores maiores tendem a reduzir essa razão. O valor absoluto mostra a força da influência.",
        "Esta tabela coloca números no que o gráfico tornado mostra visualmente. A correlação de Spearman varia de -1 a +1 e mede se, quando uma variável aumenta nas simulações, a maior razão valor simulado / Report Level também tende a aumentar ou diminuir. A ordenação usa |correlação|, por isso uma variável com -0,80 aparece como muito influente mesmo tendo efeito redutor.",
        table_key="sensitivity_influence",
    )


def _sensitivity_results_table(sensitivity: dict[str, Any]) -> str:
    rows = []
    for item in sensitivity.get("summary_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('compartment') or '')}</td>"
            f"<td>{escape(item.get('mean_text') or '—')}</td>"
            f"<td>{escape(item.get('min_text') or '—')}</td>"
            f"<td>{escape(item.get('max_text') or '—')}</td>"
            f"<td>{escape(item.get('p95_text') or '—')}</td>"
            f"<td>{escape(item.get('report_level_text') or '—')}</td>"
            f"<td>{escape(item.get('p95_report_level_ratio_text') or '—')}</td>"
            f"<td>{escape(item.get('exceedance_probability_text') or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Resumo dos resultados simulados por radionuclídeo e compartimento",
        "<tr><th>Radionuclídeo</th><th>Compartimento</th><th>Média</th><th>Mínimo</th><th>Máximo</th><th>P95</th><th>Report Level</th><th>P95 / Report Level</th><th>Prob. > Report Level</th></tr>",
        "".join(rows),
        "A probabilidade empírica é calculada como número de simulações acima do Report Level dividido pelo número total de simulações. Quando não há Report Level cadastrado para o radionuclídeo e o compartimento, a probabilidade fica sem referência.",
        "Esta tabela consolida os resultados de todas as rodadas por radionuclídeo e compartimento. O P95 é o percentil 95: após ordenar as simulações do menor para o maior, ele é o valor abaixo do qual ficam 95% dos cenários. A probabilidade empírica de ultrapassar o Report Level é a fração das simulações que ficaram acima da referência, por exemplo 230 ultrapassagens em 10.000 simulações equivalem a 2,3%.",
        table_key="sensitivity_results",
    )


def _sensitivity_tornado_svg(sensitivity: dict[str, Any]) -> str:
    rows = (sensitivity.get("chart_payloads") or {}).get("tornado", {}).get("rows") or []
    width = 760
    left = 260
    right = 80
    top = 34
    row_height = 34
    height = top + max(1, len(rows)) * row_height + 28
    bar_width = width - left - right
    parts = [
        f'<svg class="tar-chart tar-chart--wide" data-chart="sensitivity-tornado" viewBox="0 0 {width} {height}" role="img" aria-label="Gráfico tornado da análise de sensibilidade">',
        f'<line x1="{left}" y1="18" x2="{left + bar_width}" y2="18" stroke="#c9d7dc"/>',
        f'<text x="{left}" y="12" font-size="11" fill="#607782">0</text>',
        f'<text x="{left + bar_width}" y="12" text-anchor="end" font-size="11" fill="#607782">|ρ| = 1</text>',
    ]
    for index, row in enumerate(rows):
        y = top + index * row_height
        absolute = max(0.0, min(1.0, float(row.get("absolute_correlation") or 0.0)))
        corr = float(row.get("correlation") or 0.0)
        color = "#27667b" if corr >= 0 else "#b8672a"
        label = row.get("label") or ""
        bar = max(2, absolute * bar_width)
        parts.extend(
            [
                f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" font-size="12" fill="#17313a">{escape(label)}</text>',
                f'<rect x="{left}" y="{y + 6}" width="{bar:.2f}" height="18" rx="4" fill="{color}"/>',
                f'<text x="{left + bar + 8:.2f}" y="{y + 20}" font-size="11" fill="#516873">{escape(row.get("correlation_text") or "—")}</text>',
            ]
        )
    parts.append("</svg>")
    return "".join(parts)


def _heatmap_color(probability: Any) -> str:
    if probability is None:
        return "#eef2f4"
    value = max(0.0, min(1.0, float(probability)))
    if value <= 0.01:
        return "#e8f3ee"
    if value <= 0.05:
        return "#c7e6d2"
    if value <= 0.20:
        return "#f2d27a"
    if value <= 0.50:
        return "#df8a4a"
    return "#b8423a"


def _sensitivity_heatmap_svg(sensitivity: dict[str, Any]) -> str:
    payload = (sensitivity.get("chart_payloads") or {}).get("heatmap") or {}
    radionuclides = payload.get("radionuclides") or []
    compartments = payload.get("compartments") or []
    cells = {
        (cell.get("radionuclide"), cell.get("compartment_key")): cell
        for cell in payload.get("cells") or []
    }
    cell_width = 118
    cell_height = 28
    left = 96
    top = 42
    width = left + len(compartments) * cell_width + 24
    height = top + len(radionuclides) * cell_height + 34
    parts = [
        f'<svg class="tar-chart tar-chart--wide" data-chart="sensitivity-heatmap" viewBox="0 0 {width} {height}" role="img" aria-label="Heatmap de probabilidade de ultrapassar Report Level">',
    ]
    for col, compartment in enumerate(compartments):
        x = left + col * cell_width + cell_width / 2
        parts.append(f'<text x="{x:.1f}" y="24" text-anchor="middle" font-size="11" fill="#17313a">{escape(compartment.get("label") or "")}</text>')
    for row_index, radionuclide in enumerate(radionuclides):
        y = top + row_index * cell_height
        parts.append(f'<text x="{left - 10}" y="{y + 18}" text-anchor="end" font-size="11" fill="#17313a">{escape(radionuclide)}</text>')
        for col, compartment in enumerate(compartments):
            x = left + col * cell_width
            cell = cells.get((radionuclide, compartment.get("key"))) or {}
            probability = cell.get("probability")
            text = cell.get("probability_text") or "—"
            parts.extend(
                [
                    f'<rect x="{x}" y="{y}" width="{cell_width - 4}" height="{cell_height - 4}" rx="4" fill="{_heatmap_color(probability)}" stroke="#ffffff"/>',
                    f'<text x="{x + (cell_width - 4) / 2:.1f}" y="{y + 17}" text-anchor="middle" font-size="10" fill="#17313a">{escape(text)}</text>',
                ]
            )
    parts.append("</svg>")
    return "".join(parts)


def _sensitivity_histogram_svg(sensitivity: dict[str, Any]) -> str:
    payload = (sensitivity.get("chart_payloads") or {}).get("histogram") or {}
    bins = payload.get("bins") or []
    width = 760
    height = 260
    left = 54
    right = 28
    top = 28
    bottom = 52
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_count = max([int(item.get("count") or 0) for item in bins] + [1])
    lower = min([float(item.get("start") or 0) for item in bins] + [0.0])
    upper = max([float(item.get("end") or 1) for item in bins] + [1.0])
    if upper <= lower:
        upper = lower + 1.0
    parts = [
        f'<svg class="tar-chart tar-chart--wide" data-chart="sensitivity-histogram" viewBox="0 0 {width} {height}" role="img" aria-label="Histograma da maior razão simulada contra Report Level">',
        f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" rx="6" fill="#f7fafb" stroke="#d8e2e6"/>',
    ]
    for index, item in enumerate(bins):
        count = int(item.get("count") or 0)
        bar_height = 0 if max_count <= 0 else (count / max_count) * (plot_height - 12)
        x = left + index * (plot_width / max(1, len(bins)))
        bar_w = (plot_width / max(1, len(bins))) - 4
        y = top + plot_height - bar_height
        parts.append(f'<rect x="{x + 2:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{bar_height:.2f}" fill="#27667b"/>')
        if index % 3 == 0:
            parts.append(f'<text x="{x + bar_w / 2:.2f}" y="{height - 26}" text-anchor="middle" font-size="9" fill="#607782">{escape(item.get("label") or "")}</text>')
    reference = float(payload.get("reference") or 1.0)
    if lower <= reference <= upper:
        ref_x = left + ((reference - lower) / (upper - lower)) * plot_width
        parts.extend(
            [
                f'<line x1="{ref_x:.2f}" y1="{top}" x2="{ref_x:.2f}" y2="{top + plot_height}" stroke="#b8423a" stroke-width="2" stroke-dasharray="5 5"/>',
                f'<text x="{ref_x + 6:.2f}" y="{top + 14}" font-size="10" fill="#b8423a">Report Level</text>',
            ]
        )
    parts.extend(
        [
            f'<text x="{left + plot_width / 2}" y="{height - 6}" text-anchor="middle" font-size="11" fill="#17313a">Maior razão valor simulado / Report Level por simulação</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


def _sensitivity_boxplot_svg(sensitivity: dict[str, Any]) -> str:
    payload = (sensitivity.get("chart_payloads") or {}).get("boxplot") or {}
    stats = payload.get("stats") or {}
    values = [
        stats.get("min"),
        stats.get("q1"),
        stats.get("median"),
        stats.get("q3"),
        stats.get("max"),
        stats.get("p95"),
        payload.get("reference") or 1.0,
    ]
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return ""
    width = 760
    height = 170
    left = 70
    right = 34
    axis_y = 84
    plot_width = width - left - right
    lower = min(0.0, min(numeric))
    upper = max(numeric)
    if upper <= lower:
        upper = lower + 1.0

    def x_at(value: Any) -> float:
        return left + ((float(value) - lower) / (upper - lower)) * plot_width

    min_x = x_at(stats.get("min") or lower)
    q1_x = x_at(stats.get("q1") or lower)
    median_x = x_at(stats.get("median") or lower)
    q3_x = x_at(stats.get("q3") or lower)
    max_x = x_at(stats.get("max") or upper)
    p95_x = x_at(stats.get("p95") or upper)
    ref_x = x_at(payload.get("reference") or 1.0)
    parts = [
        f'<svg class="tar-chart tar-chart--wide" data-chart="sensitivity-boxplot" viewBox="0 0 {width} {height}" role="img" aria-label="Boxplot da maior razão simulada contra Report Level">',
        f'<line x1="{left}" y1="{axis_y}" x2="{left + plot_width}" y2="{axis_y}" stroke="#d8e2e6"/>',
        f'<line x1="{min_x:.2f}" y1="{axis_y}" x2="{q1_x:.2f}" y2="{axis_y}" stroke="#27667b" stroke-width="2"/>',
        f'<line x1="{q3_x:.2f}" y1="{axis_y}" x2="{max_x:.2f}" y2="{axis_y}" stroke="#27667b" stroke-width="2"/>',
        f'<line x1="{min_x:.2f}" y1="{axis_y - 18}" x2="{min_x:.2f}" y2="{axis_y + 18}" stroke="#27667b" stroke-width="2"/>',
        f'<line x1="{max_x:.2f}" y1="{axis_y - 18}" x2="{max_x:.2f}" y2="{axis_y + 18}" stroke="#27667b" stroke-width="2"/>',
        f'<rect x="{q1_x:.2f}" y="{axis_y - 24}" width="{max(2, q3_x - q1_x):.2f}" height="48" rx="5" fill="#d9ecf1" stroke="#27667b" stroke-width="2"/>',
        f'<line x1="{median_x:.2f}" y1="{axis_y - 24}" x2="{median_x:.2f}" y2="{axis_y + 24}" stroke="#17313a" stroke-width="3"/>',
        f'<line x1="{p95_x:.2f}" y1="{axis_y - 30}" x2="{p95_x:.2f}" y2="{axis_y + 30}" stroke="#6b4aa0" stroke-width="2" stroke-dasharray="4 4"/>',
        f'<text x="{p95_x + 6:.2f}" y="{axis_y - 34}" font-size="10" fill="#6b4aa0">P95 {escape(stats.get("p95_text") or "—")}</text>',
        f'<line x1="{ref_x:.2f}" y1="28" x2="{ref_x:.2f}" y2="{height - 36}" stroke="#b8423a" stroke-width="2" stroke-dasharray="5 5"/>',
        f'<text x="{ref_x + 6:.2f}" y="24" font-size="10" fill="#b8423a">Report Level = 1</text>',
        f'<text x="{min_x:.2f}" y="{height - 20}" text-anchor="middle" font-size="10" fill="#607782">mín {escape(stats.get("min_text") or "—")}</text>',
        f'<text x="{median_x:.2f}" y="{height - 44}" text-anchor="middle" font-size="10" fill="#17313a">mediana {escape(stats.get("median_text") or "—")}</text>',
        f'<text x="{max_x:.2f}" y="{height - 20}" text-anchor="middle" font-size="10" fill="#607782">máx {escape(stats.get("max_text") or "—")}</text>',
        f'<text x="{left + plot_width / 2}" y="{height - 4}" text-anchor="middle" font-size="11" fill="#17313a">Maior razão valor simulado / Report Level</text>',
        "</svg>",
    ]
    return "".join(parts)


def _sensitivity_panel(summary: dict[str, Any]) -> str:
    sensitivity = (summary.get("scenario") or {}).get("sensitivity") or {}
    if not sensitivity:
        return ""
    return f"""
<section class="panel">
  <h2>Análise de sensibilidade Monte Carlo</h2>
  <p>{escape(sensitivity.get('narrative_text') or '')}</p>
  <div class="cards sensitivity-cards">{_sensitivity_cards(sensitivity)}</div>
  {_sensitivity_distribution_explanation()}
  {_sensitivity_variables_table(sensitivity)}
  <div class="sensitivity-chart-grid">
    <article>
      <h3>Influência das variáveis</h3>
      {_explain_text("O gráfico tornado é um ranking visual de influência. Para cada rodada, o sistema calcula a maior razão valor simulado / Report Level; depois mede, por correlação de Spearman, quais variáveis mais acompanham essa razão. Spearman usa a ordem dos valores, não exige relação linear perfeita e varia de -1 a +1. No tornado, usamos o valor absoluto: barras maiores indicam maior influência, seja para aumentar ou reduzir a proximidade com o Report Level.")}
      {_sensitivity_tornado_svg(sensitivity)}
    </article>
    <article>
      <h3>Probabilidade de ultrapassar Report Level</h3>
      {_explain_text("O heatmap responde uma pergunta direta: em quantas rodadas aquele radionuclídeo e compartimento ficou acima do Report Level? A porcentagem é empírica porque vem da contagem das simulações, por exemplo 230 ultrapassagens em 10.000 rodadas equivalem a 2,3%. Células mais quentes indicam maior frequência de superação; células com travessão não têm Report Level cadastrado.")}
      {_sensitivity_heatmap_svg(sensitivity)}
    </article>
    <article>
      <h3>Distribuição da maior razão simulada</h3>
      {_explain_text("O histograma resume, rodada a rodada, a maior razão observada entre valor simulado e Report Level. A linha em 1,0 marca o ponto em que a simulação encosta ou ultrapassa a referência.")}
      {_sensitivity_histogram_svg(sensitivity)}
    </article>
    <article>
      <h3>Boxplot da maior razão simulada</h3>
      {_explain_text("O boxplot mostra a mesma variável do histograma de forma compacta: a caixa contém os 50% centrais das rodadas, a linha interna é a mediana, as hastes mostram mínimo e máximo, e a linha tracejada roxa marca o P95. Ele ajuda a ver rapidamente se a distribuição fica concentrada abaixo ou acima do Report Level = 1.")}
      {_sensitivity_boxplot_svg(sensitivity)}
    </article>
  </div>
  {_sensitivity_influence_table(sensitivity)}
  {_sensitivity_results_table(sensitivity)}
</section>
"""


def _stat_source_rows_table(statistical: dict[str, Any], rows_key: str, caption: str, intro: str) -> str:
    rows = []
    for item in statistical.get(rows_key) or []:
        if rows_key == "norm_rows":
            rows.append(
                "<tr>"
                f"<td>{escape(item.get('radionuclide') or '')}</td>"
                f"<td>{escape(item.get('compartment') or '')}</td>"
                f"<td>{escape(item.get('reference') or '')}</td>"
                f"<td>{escape(item.get('value_text') or '—')}</td>"
                f"<td>{escape(item.get('unit') or '')}</td>"
                "</tr>"
            )
        else:
            rows.append(
                "<tr>"
                f"<td>{escape(item.get('radionuclide') or '')}</td>"
                f"<td>{escape(item.get('compartment') or '')}</td>"
                f"<td>{escape(item.get('value_text') or '—')}</td>"
                f"<td>{escape(item.get('unit') or '')}</td>"
                f"<td>{escape(item.get('method') or '')}</td>"
                "</tr>"
            )
    if rows_key == "norm_rows":
        header = "<tr><th>Radionuclídeo</th><th>Compartimento</th><th>Referência</th><th>Valor normativo</th><th>Unidade</th></tr>"
    else:
        header = "<tr><th>Radionuclídeo</th><th>Compartimento</th><th>Valor base</th><th>Unidade</th><th>Origem</th></tr>"
    table_keys = {
        "calculated_rows": "stat_calculated",
        "erica_rows": "stat_erica",
        "norm_rows": "stat_norms",
    }
    return _tar_table(
        "tar-table--dense",
        caption,
        header,
        "".join(rows),
        "Os valores normativos são fixos; os valores calculados e ERICA são bases determinísticas ou estimadas, sem replicações aleatórias.",
        intro,
        table_key=table_keys.get(rows_key, ""),
    )


def _stat_descriptive_table(statistical: dict[str, Any]) -> str:
    rows = []
    for item in statistical.get("descriptive_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('dataset') or '')}</td>"
            f"<td>{escape(item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('compartment') or '')}</td>"
            f"<td>{escape(str(item.get('n') or '—'))}</td>"
            f"<td>{escape(item.get('mean_text') or '—')}</td>"
            f"<td>{escape(item.get('median_text') or '—')}</td>"
            f"<td>{escape(item.get('stdev_text') or '—')}</td>"
            f"<td>{escape(item.get('q1_text') or '—')}</td>"
            f"<td>{escape(item.get('q3_text') or '—')}</td>"
            f"<td>{escape(item.get('p95_text') or '—')}</td>"
            f"<td>{escape(item.get('cv_text') or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Estatística descritiva dos valores calculados e estimados",
        "<tr><th>Conjunto</th><th>Radionuclídeo</th><th>Compartimento</th><th>n</th><th>Média</th><th>Mediana</th><th>Desvio-padrão</th><th>Q1</th><th>Q3</th><th>P95</th><th>CV</th></tr>",
        "".join(rows),
        "A estatística usa os valores disponíveis por radionuclídeo e compartimento; não há aumento artificial de N por sorteio.",
        "Esta tabela apresenta estatística descritiva para os dados calculados por fórmulas e para os dados estimados pelo ERICA Tool. A norma não é randomizada: Report Level e LLD são referências fixas.",
        table_key="stat_descriptive",
    )


def _stat_inferential_table(statistical: dict[str, Any]) -> str:
    rows = []
    for item in statistical.get("inferential_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('dataset') or '')}</td>"
            f"<td>{escape(item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('compartment') or '')}</td>"
            f"<td>{escape(item.get('reference') or '')}</td>"
            f"<td>{escape(str(item.get('n') or '—'))}</td>"
            f"<td>{escape(item.get('shapiro_p_text') or '—')}</td>"
            f"<td>{escape(item.get('test_label') or '—')}</td>"
            f"<td>{escape(item.get('p_value_text') or '—')}</td>"
            f"<td>{escape(item.get('p95_ratio_text') or '—')}</td>"
            f"<td>{escape(item.get('exceedance_rate_text') or '—')}</td>"
            f"<td>{escape(item.get('conclusion') or '')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Estatística inferencial contra Report Level e LLD",
        "<tr><th>Conjunto</th><th>Radionuclídeo</th><th>Compartimento</th><th>Norma</th><th>n</th><th>Shapiro-Wilk</th><th>Teste</th><th>p-value</th><th>P95 razão</th><th>Ultrapassagem</th><th>Conclusão exploratória</th></tr>",
        "".join(rows),
        "O teste usa log(valor / referência). A hipótese alternativa é ficar abaixo da norma; a norma permanece determinística.",
        "Esta tabela mostra a estatística inferencial dos dados calculados por fórmulas e dos dados simulados pelo ERICA Tool contra as referências normativas disponíveis.",
        table_key="stat_inferential",
    )


def _stat_paired_table(statistical: dict[str, Any]) -> str:
    rows = []
    for item in statistical.get("paired_comparison_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('scope') or item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('compartment') or '')}</td>"
            f"<td>{escape(str(item.get('n') or '—'))}</td>"
            f"<td>{escape(item.get('median_ratio_text') or '—')}</td>"
            f"<td>{escape(item.get('ci95_low_text') or '—')} - {escape(item.get('ci95_high_text') or '—')}</td>"
            f"<td>{escape(item.get('test_label') or '—')}</td>"
            f"<td>{escape(item.get('p_value_text') or '—')}</td>"
            f"<td>{escape(item.get('conclusion') or item.get('reason') or '')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Comparação pareada: calculado por fórmulas vs ERICA Tool",
        "<tr><th>Escopo</th><th>Compartimento</th><th>n</th><th>Mediana calculado/ERICA</th><th>IC95% da razão média</th><th>Teste</th><th>p-value</th><th>Conclusão</th></tr>",
        "".join(rows),
        "A comparação pareada usa log(calculado / ERICA) e tem finalidade exploratória; os valores do ERICA são estimativas visuais até substituição por saídas reais.",
        "Esta tabela avalia a compatibilidade exploratória entre os resultados calculados pela planilha e os resultados estimados pelo ERICA Tool.",
        table_key="stat_paired",
    )


def _empirical_cards(empirical: dict[str, Any]) -> str:
    return "".join(
        f'<div class="card"><span>{escape(str(card.get("label") or ""))}</span><strong>{escape(str(card.get("value") or "—"))}</strong></div>'
        for card in empirical.get("cards") or []
    )


def _empirical_group_table(empirical: dict[str, Any]) -> str:
    rows = []
    for item in empirical.get("groups") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('group') or '')}</td>"
            f"<td>{escape(str(item.get('sample_count') or 0))}</td>"
            f"<td>{escape(str(item.get('activity_detected_count') or 0))}</td>"
            f"<td>{escape(str(item.get('activity_censored_count') or 0))}</td>"
            f"<td>{escape(str(item.get('activity_missing_count') or 0))}</td>"
            f"<td>{escape(item.get('activity_mean_text') or '—')}</td>"
            f"<td>{escape(item.get('activity_median_text') or '—')}</td>"
            f"<td>{escape(item.get('activity_p95_text') or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Resumo por grupo de amostras",
        "<tr><th>Grupo</th><th>Amostras</th><th>A-TAR detectado</th><th>A-TAR &lt; MDA</th><th>A-TAR ausente</th><th>Média A-TAR</th><th>Mediana A-TAR</th><th>P95 A-TAR</th></tr>",
        "".join(rows),
        empirical.get("mda_policy") or "",
        "Esta tabela separa as amostras reais do TAR por afluente e efluente antes de qualquer cálculo por fórmula.",
        table_key="empirical_groups",
    )


def _empirical_radionuclide_table(empirical: dict[str, Any]) -> str:
    rows = []
    for item in empirical.get("radionuclide_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('group') or '')}</td>"
            f"<td>{escape(item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('model_status') or '')}</td>"
            f"<td>{escape(str(item.get('sample_count') or 0))}</td>"
            f"<td>{escape(str(item.get('detected_count') or 0))}</td>"
            f"<td>{escape(str(item.get('censored_count') or 0))}</td>"
            f"<td>{escape(str(item.get('missing_count') or 0))}</td>"
            f"<td>{escape(item.get('detected_rate_text') or '—')}</td>"
            f"<td>{escape(item.get('mean_text') or '—')}</td>"
            f"<td>{escape(item.get('median_text') or '—')}</td>"
            f"<td>{escape(item.get('p95_text') or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Estatística descritiva por radionuclídeo observado",
        "<tr><th>Grupo</th><th>Radionuclídeo</th><th>Status no modelo</th><th>Amostras</th><th>Detectados</th><th>&lt; MDA</th><th>Ausentes</th><th>Taxa detectada</th><th>Média</th><th>Mediana</th><th>P95</th></tr>",
        "".join(rows),
        "Nb-95 permanece como observado não modelado porque não há linha equivalente na fórmula da planilha TAR atual.",
        "Esta tabela usa os valores numéricos medidos na planilha de atividade total; entradas < MDA> só contam como censura.",
        table_key="empirical_radionuclides",
    )


def _empirical_modeled_table(empirical: dict[str, Any]) -> str:
    rows = []
    for item in empirical.get("modeled_compartment_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('group') or '')}</td>"
            f"<td>{escape(item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('compartment') or '')}</td>"
            f"<td>{escape(str(item.get('n') or '—'))}</td>"
            f"<td>{escape(item.get('mean_text') or '—')}</td>"
            f"<td>{escape(item.get('median_text') or '—')}</td>"
            f"<td>{escape(item.get('p95_text') or '—')}</td>"
            f"<td>{escape(item.get('report_level_text') or '—')}</td>"
            f"<td>{escape(item.get('report_level_p95_ratio_text') or '—')}</td>"
            f'<td><span class="pill {_status_class(str(item.get("report_level_status") or ""))}">{escape(item.get("report_level_status") or "—")}</span></td>'
            f"<td>{escape(item.get('report_level_exceedance_rate_text') or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Resultados calculados por fórmula a partir das amostras reais",
        "<tr><th>Grupo</th><th>Radionuclídeo</th><th>Compartimento</th><th>n</th><th>Média</th><th>Mediana</th><th>P95</th><th>Report Level</th><th>P95 / Report Level</th><th>Status</th><th>Freq. &gt; Report Level</th></tr>",
        "".join(rows),
        "As frações Si foram calculadas por amostra a partir dos radionuclídeos detectados; < MDA> não participa do denominador.",
        "Esta tabela aplica aos dados reais a mesma lógica da planilha: atividade do radionuclídeo, vazão de diluição e fatores de compartimento ambiental.",
        table_key="empirical_modeled",
    )


def _empirical_inferential_table(empirical: dict[str, Any]) -> str:
    rows = []
    for item in empirical.get("inferential_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('group') or '')}</td>"
            f"<td>{escape(item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('compartment') or '')}</td>"
            f"<td>{escape(str(item.get('n') or '—'))}</td>"
            f"<td>{escape(item.get('reference_value_text') or '—')}</td>"
            f"<td>{escape(item.get('p95_ratio_text') or '—')}</td>"
            f"<td>{escape(str(item.get('exceedance_count') if item.get('exceedance_count') is not None else '—'))}</td>"
            f"<td>{escape(item.get('exceedance_rate_text') or '—')}</td>"
            f"<td>{escape(item.get('exceedance_ci95_text') or '—')}</td>"
            f"<td>{escape(item.get('test_label') or '—')}</td>"
            f"<td>{escape(item.get('p_value_text') or '—')}</td>"
            f"<td>{escape(item.get('conclusion') or item.get('reason') or '')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Inferência com dados reais do TAR - Afluente contra Report Level fixo",
        "<tr><th>Grupo</th><th>Radionuclídeo</th><th>Compartimento</th><th>n</th><th>Report Level</th><th>P95 razão</th><th>Ultrapassagens</th><th>Freq. &gt; Report Level</th><th>IC95% freq.</th><th>Teste</th><th>p-value</th><th>Conclusão</th></tr>",
        "".join(rows),
        "O Report Level é referência fixa. O IC95% é binomial para a frequência observada de ultrapassagem; o p-value usa log(valor/Report Level) quando há n suficiente.",
        "Esta tabela substitui as replicações aleatórias por inferência baseada nas amostras reais do TAR - Afluente calculadas pela fórmula da planilha.",
        table_key="empirical_inferential",
    )


def _empirical_activity_panel(summary: dict[str, Any]) -> str:
    empirical = (summary.get("scenario") or {}).get("empirical_activity_statistics") or {}
    if not empirical:
        return ""
    unmodeled = ", ".join(empirical.get("unmodeled_radionuclides") or []) or "nenhum"
    return f"""
<section class="panel report-block" id="dados-reais-tar">
  <h2>Dados reais de atividade total TAR</h2>
  <article class="report-block-child" id="dados-reais-entrada">
    <h3>Entrada e organização das amostras</h3>
    <p>{escape(empirical.get('narrative_text') or '')}</p>
    <p class="table-note">Fonte: {escape(str(empirical.get('source_workbook_path') or ''))}, aba {escape(str(empirical.get('source_sheet') or ''))}. Radionuclídeos observados não modelados: {escape(unmodeled)}.</p>
    <div class="cards sensitivity-cards">{_empirical_cards(empirical)}</div>
    {_empirical_group_table(empirical)}
    {_empirical_radionuclide_table(empirical)}
  </article>
  <article class="report-block-child" id="dados-reais-calculos">
    <h3>Cálculos por fórmula a partir dos dados reais</h3>
    <p>Este bloco aplica a mesma lógica da planilha TAR às amostras reais, separando radionuclídeo e compartimento ambiental.</p>
    {_empirical_modeled_table(empirical)}
  </article>
  <article class="report-block-child" id="dados-reais-inferencia">
    <h3>Inferência com dados reais contra Report Level</h3>
    <p>A estatística inferencial desta seção usa somente amostras reais do TAR - Afluente calculadas pela fórmula; o Report Level permanece referência fixa.</p>
    {_empirical_inferential_table(empirical)}
  </article>
</section>
"""


def _total_activity_review_cards(review: dict[str, Any]) -> str:
    return "".join(
        f'<div class="card"><span>{escape(str(card.get("label") or ""))}</span><strong>{escape(str(card.get("value") or "—"))}</strong></div>'
        for card in review.get("cards") or []
    )


def _total_activity_top15_table(review: dict[str, Any]) -> str:
    rows = []
    for item in review.get("top15_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('rank') or '—'))}</td>"
            f"<td>{escape(item.get('date') or '')}</td>"
            f"<td>{escape(item.get('activity_total_text') or '—')}</td>"
            f"<td>{escape(item.get('sample_id') or '—')}</td>"
            f"<td>{escape(item.get('group') or '—')}</td>"
            f'<td><span class="pill {_status_class("abaixo" if item.get("complete") else "sem referência")}">{escape(item.get("status") or "—")}</span></td>'
            f"<td>{escape(str(item.get('numeric_count') or 0))}</td>"
            f"<td>{escape(str(item.get('censored_count') or 0))}</td>"
            f"<td>{escape(str(item.get('missing_count') or 0))}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Auditoria das 15 maiores atividades totais do tanque",
        "<tr><th>Rank</th><th>Data</th><th>A-TAR</th><th>Amostra</th><th>Grupo</th><th>Status</th><th>Numéricos</th><th>&lt; MDA</th><th>Ausentes</th></tr>",
        "".join(rows),
        review.get("source_note") or "",
        table_key="total_activity_top15",
    )


def _total_activity_complete_table(review: dict[str, Any]) -> str:
    rows = []
    for item in review.get("window_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('anchor_date') or '')}</td>"
            f"<td>{escape(item.get('window_start_date') or '—')} a {escape(item.get('window_end_date') or '—')}</td>"
            f"<td>{escape(item.get('window_span_days_text') or '—')}</td>"
            f"<td>{escape(item.get('activity_total_text') or '—')}</td>"
            f"<td>{escape(str(item.get('numeric_count') or 0))}</td>"
            f"<td>{escape(', '.join(item.get('censored_radionuclides') or []) or '—')}</td>"
            f"<td>{escape(', '.join(item.get('covered_radionuclides') or []) or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Janelas mínimas usadas nos cálculos",
        "<tr><th>Data âncora</th><th>Janela</th><th>Dias</th><th>A-TAR máx.</th><th>Numéricos</th><th>&lt; MDA</th><th>Radionuclídeos cobertos</th></tr>",
        "".join(rows),
        review.get("mda_policy") or "",
        table_key="total_activity_complete",
    )


def _total_activity_formula_table(review: dict[str, Any]) -> str:
    rows = []
    for item in review.get("formula_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('name') or '')}</td>"
            f"<td>{escape(item.get('symbol') or '')}</td>"
            f"<td><code>{escape(item.get('formula') or '')}</code></td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Fórmulas aplicadas às linhas completas",
        "<tr><th>Cálculo</th><th>Símbolo</th><th>Fórmula</th></tr>",
        "".join(rows),
        table_key="total_activity_formulas",
    )


def _total_activity_constants_table(review: dict[str, Any]) -> str:
    rows = []
    for item in review.get("constant_rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(item.get('radionuclide') or '')}</td>"
            f"<td>{escape(item.get('scenario_flow_text') or '—')}</td>"
            f"<td>{escape(item.get('decay_constant_h_text') or '—')}</td>"
            f"<td>{escape(item.get('half_life_h_text') or '—')}</td>"
            f"<td>{escape(item.get('bioaccumulation_fish_text') or '—')}</td>"
            f"<td>{escape(item.get('bioaccumulation_invertebrate_text') or '—')}</td>"
            f"<td>{escape(item.get('kd_sediment_l_kg_text') or '—')}</td>"
            f"<td>{escape(item.get('sediment_transfer_factor_text') or '—')}</td>"
            f"<td>{escape(item.get('sediment_exposure_time_h_text') or '—')}</td>"
            "</tr>"
        )
    return _tar_table(
        "tar-table--dense",
        "Constantes e fatores da planilha TAR",
        "<tr><th>Radionuclídeo</th><th>Vazão</th><th>λ</th><th>Meia-vida</th><th>Bp peixe</th><th>Bp inv.</th><th>Kd</th><th>Fator sed.</th><th>Tempo</th></tr>",
        "".join(rows),
        table_key="total_activity_constants",
    )


def _total_activity_matrix_table(review: dict[str, Any]) -> str:
    source_rows = list(review.get("matrix_rows") or [])
    grouped_rows = _group_by_radionuclide_matrix(source_rows)
    summary_rows = []
    detail_blocks = []
    for index, ((radionuclide, _compartment_key, compartment), group_rows) in enumerate(grouped_rows):
        values = _numeric_values(group_rows, "value")
        summary_rows.append(
            "<tr>"
            f"<td>{escape(radionuclide)}</td>"
            f"<td>{escape(compartment)}</td>"
            f"<td>{len(group_rows)}</td>"
            f"<td>{_distinct_count(group_rows, 'anchor_date')}</td>"
            f"<td>{escape(group_rows[0].get('unit') or '')}</td>"
            f"<td>{escape(_mean_text(values))}</td>"
            f"<td>{escape(_min_max_text(values))}</td>"
            "</tr>"
        )
        detail_rows = []
        for item in group_rows:
            detail_rows.append(
                "<tr>"
                f"<td>{escape(item.get('anchor_date') or '')}</td>"
                f"<td>{escape(item.get('window_start_date') or '—')} a {escape(item.get('window_end_date') or '—')}</td>"
                f"<td>{escape(item.get('source_date') or '')}</td>"
                f"<td>{escape(item.get('source_sample_id') or item.get('sample_id') or '')}</td>"
                f"<td>{escape(item.get('fraction_text') or '—')}</td>"
                f"<td>{escape(item.get('activity_bq_text') or '—')}</td>"
                f"<td>{escape(item.get('value_text') or '—')}</td>"
                f"<td>{escape(item.get('unit') or '')}</td>"
                "</tr>"
            )
        detail_table = _tar_table(
            "tar-table--dense tar-table--detail",
            f"Detalhe calculado - {radionuclide} - {compartment}",
            "<tr><th>Data âncora</th><th>Janela</th><th>Data fonte</th><th>Amostra fonte</th><th>Si</th><th>Ai</th><th>Resultado</th><th>Unidade</th></tr>",
            "".join(detail_rows),
            intro=(
                f"Esta tabela detalha os cálculos individuais de {radionuclide} em {compartment}. "
                "Ela mostra a data âncora, a janela usada para localizar o radionuclídeo, a fração Si, a atividade Ai e o resultado final na unidade da matriz."
            ),
        )
        detail_blocks.append(
            _details_section(
                f"{radionuclide} - {compartment} ({len(group_rows)} linhas)",
                detail_table,
                open_by_default=index == 0,
            )
        )
    summary_table = _tar_table(
        "tar-table--dense tar-table--summary",
        "Resultados calculados por data, radionuclídeo e matriz",
        "<tr><th>Radionuclídeo</th><th>Matriz</th><th>Linhas</th><th>Datas âncora</th><th>Unidade</th><th>Média</th><th>Mín. a máx.</th></tr>",
        "".join(summary_rows),
        "Os detalhes ficam separados abaixo por radionuclídeo e matriz. Radionuclídeos < MDA> não geram resultado por matriz porque não entram como valor numérico no denominador.",
        table_key="total_activity_matrix",
    )
    details = "".join(detail_blocks)
    return f'{summary_table}<div class="tar-subsections"><h3>Detalhes por radionuclídeo e matriz</h3>{details}</div>'


def _ratio_domain(values: list[float]) -> tuple[float, float]:
    positive = [value for value in values if value and value > 0]
    if not positive:
        return 0.1, 10.0
    lower = min([1.0, *positive])
    upper = max([1.0, *positive])
    lower_power = math.floor(math.log10(lower))
    upper_power = math.ceil(math.log10(upper))
    if lower_power == upper_power:
        upper_power += 1
    return 10**lower_power, 10**upper_power


def _log_position(value: float, lower: float, upper: float, start: float, size: float, *, invert: bool = False) -> float:
    safe_value = max(lower, min(upper, value))
    lower_log = math.log10(lower)
    upper_log = math.log10(upper)
    if upper_log <= lower_log:
        return start
    ratio = (math.log10(safe_value) - lower_log) / (upper_log - lower_log)
    return start + (1 - ratio) * size if invert else start + ratio * size


def _chart_color(label: str) -> str:
    palette = {
        "Água": "#27667b",
        "Peixe": "#2d8577",
        "Invertebrado": "#9b6a2f",
        "Sedimento": "#6b4aa0",
    }
    return palette.get(label, "#52616a")


def _erica_chart_scopes(review: dict[str, Any]) -> list[dict[str, Any]]:
    return (review.get("erica_chart_payloads") or {}).get("scope_rows") or []


def _erica_ratio_boxplot_svg(review: dict[str, Any]) -> str:
    scopes = _erica_chart_scopes(review)
    values: list[float] = []
    for scope in scopes:
        stats = scope.get("stats") or {}
        values.extend(float(stats[key]) for key in ["min", "q1", "median", "q3", "max", "p95"] if stats.get(key) is not None and float(stats[key]) > 0)
    lower, upper = _ratio_domain(values)
    width = 860
    left = 132
    right = 42
    top = 58
    row_height = 54
    height = top + max(1, len(scopes)) * row_height + 56
    plot_width = width - left - right
    ref_x = _log_position(1.0, lower, upper, left, plot_width)
    parts = [
        f'<svg class="tar-chart tar-chart--wide" data-chart="erica-boxplot" viewBox="0 0 {width} {height}" role="img" aria-label="Boxplot da razão calculado por fórmulas sobre ERICA Tool">',
        f'<text x="24" y="24" font-size="16" font-weight="700" fill="#1d252c">Boxplot da razão calculado / ERICA</text>',
        f'<line x1="{left}" y1="38" x2="{left + plot_width}" y2="38" stroke="#d6ddd9"/>',
        f'<line x1="{ref_x:.2f}" y1="42" x2="{ref_x:.2f}" y2="{height - 32}" stroke="#b8423a" stroke-width="2" stroke-dasharray="5 5"/>',
        f'<text x="{ref_x + 6:.2f}" y="54" font-size="11" fill="#b8423a">razão = 1</text>',
    ]
    for index, scope in enumerate(scopes):
        stats = scope.get("stats") or {}
        y = top + index * row_height
        label = str(scope.get("scope_label") or "")
        if not stats.get("n"):
            continue
        min_x = _log_position(float(stats["min"]), lower, upper, left, plot_width)
        q1_x = _log_position(float(stats["q1"]), lower, upper, left, plot_width)
        median_x = _log_position(float(stats["median"]), lower, upper, left, plot_width)
        q3_x = _log_position(float(stats["q3"]), lower, upper, left, plot_width)
        max_x = _log_position(float(stats["max"]), lower, upper, left, plot_width)
        p95_x = _log_position(float(stats["p95"]), lower, upper, left, plot_width)
        color = _chart_color(label)
        parts.extend(
            [
                f'<text x="24" y="{y + 19}" font-size="12" fill="#1d252c">{escape(label)} (n={escape(str(scope.get("n") or 0))})</text>',
                f'<line x1="{min_x:.2f}" y1="{y + 18}" x2="{max_x:.2f}" y2="{y + 18}" stroke="{color}" stroke-width="2"/>',
                f'<line x1="{min_x:.2f}" y1="{y + 8}" x2="{min_x:.2f}" y2="{y + 28}" stroke="{color}" stroke-width="2"/>',
                f'<line x1="{max_x:.2f}" y1="{y + 8}" x2="{max_x:.2f}" y2="{y + 28}" stroke="{color}" stroke-width="2"/>',
                f'<rect x="{q1_x:.2f}" y="{y + 4}" width="{max(3, q3_x - q1_x):.2f}" height="28" fill="#eef7f3" stroke="{color}" stroke-width="2"/>',
                f'<line x1="{median_x:.2f}" y1="{y + 4}" x2="{median_x:.2f}" y2="{y + 32}" stroke="#1d252c" stroke-width="3"/>',
                f'<circle cx="{p95_x:.2f}" cy="{y + 18}" r="4" fill="#6b4aa0"/>',
                f'<text x="{left + plot_width - 150}" y="{y + 42}" font-size="10" fill="#52616a">mediana {escape(stats.get("median_text") or "—")} | P95 {escape(stats.get("p95_text") or "—")}</text>',
            ]
        )
    parts.append(f'<text x="{left + plot_width / 2}" y="{height - 8}" text-anchor="middle" font-size="11" fill="#1d252c">Escala log10 da razão calculado / ERICA</text>')
    parts.append("</svg>")
    return "".join(parts)


def _erica_ratio_scatter_svg(scope: dict[str, Any]) -> str:
    points = [point for point in scope.get("points") or [] if point.get("ratio") is not None and float(point["ratio"]) > 0]
    ratios = [float(point["ratio"]) for point in points]
    lower, upper = _ratio_domain(ratios)
    dates = sorted({str(point.get("date") or "") for point in points})
    date_index = {date: index for index, date in enumerate(dates)}
    width = 860
    height = 330
    left = 74
    right = 30
    top = 48
    bottom = 62
    plot_width = width - left - right
    plot_height = height - top - bottom
    ref_y = _log_position(1.0, lower, upper, top, plot_height, invert=True)
    parts = [
        f'<svg class="tar-chart tar-chart--wide" data-chart="erica-scatter-{escape(str(scope.get("scope_key") or ""))}" viewBox="0 0 {width} {height}" role="img" aria-label="Dispersão temporal da razão calculado sobre ERICA">',
        f'<text x="24" y="24" font-size="15" font-weight="700" fill="#1d252c">{escape(str(scope.get("scope_label") or ""))}: pontos da razão calculado / ERICA</text>',
        f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" fill="#fbfdfc" stroke="#d6ddd9"/>',
        f'<line x1="{left}" y1="{ref_y:.2f}" x2="{left + plot_width}" y2="{ref_y:.2f}" stroke="#b8423a" stroke-width="2" stroke-dasharray="5 5"/>',
        f'<text x="{left + 8}" y="{ref_y - 6:.2f}" font-size="11" fill="#b8423a">razão = 1</text>',
    ]
    if len(dates) <= 1:
        x_at = lambda _date: left + plot_width / 2
    else:
        x_at = lambda date: left + (date_index.get(str(date), 0) / (len(dates) - 1)) * plot_width
    for point in points:
        ratio = float(point["ratio"])
        cx = x_at(point.get("date"))
        cy = _log_position(ratio, lower, upper, top, plot_height, invert=True)
        color = _chart_color(str(point.get("compartment") or scope.get("scope_label") or ""))
        stroke = "#1d252c" if point.get("erica_generated") else color
        fill = "#ffffff" if point.get("erica_generated") else color
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="3.2" fill="{fill}" stroke="{stroke}" stroke-width="1">'
            f'<title>{escape(str(point.get("date") or ""))} | {escape(str(point.get("radionuclide") or ""))} | {escape(str(point.get("compartment") or ""))}: {escape(str(point.get("ratio_text") or "—"))}</title></circle>'
        )
    if dates:
        parts.extend(
            [
                f'<text x="{left}" y="{height - 30}" font-size="10" fill="#52616a">{escape(dates[0])}</text>',
                f'<text x="{left + plot_width}" y="{height - 30}" text-anchor="end" font-size="10" fill="#52616a">{escape(dates[-1])}</text>',
            ]
        )
    parts.extend(
        [
            f'<text x="{left + plot_width / 2}" y="{height - 8}" text-anchor="middle" font-size="11" fill="#1d252c">Data da amostra</text>',
            f'<text x="18" y="{top + plot_height / 2}" transform="rotate(-90 18 {top + plot_height / 2})" text-anchor="middle" font-size="11" fill="#1d252c">log10(calculado / ERICA)</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


def _erica_ratio_heatmap_svg(review: dict[str, Any]) -> str:
    heatmap = (review.get("erica_chart_payloads") or {}).get("heatmap") or {}
    radionuclides = heatmap.get("radionuclides") or []
    compartments = heatmap.get("compartments") or []
    cells = {(cell.get("radionuclide"), cell.get("compartment_key")): cell for cell in heatmap.get("cells") or []}
    cell_width = 150
    cell_height = 34
    left = 100
    top = 56
    width = left + len(compartments) * cell_width + 32
    height = top + len(radionuclides) * cell_height + 40

    def color_for(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "#eef2f4"
        if numeric < 0.5:
            return "#dceaf3"
        if numeric < 1:
            return "#e8f3ee"
        if numeric < 5:
            return "#f2d27a"
        if numeric < 50:
            return "#df8a4a"
        return "#b8423a"

    parts = [
        f'<svg class="tar-chart tar-chart--wide" data-chart="erica-heatmap" viewBox="0 0 {width} {height}" role="img" aria-label="Heatmap da mediana da razão calculado sobre ERICA">',
        '<text x="24" y="24" font-size="15" font-weight="700" fill="#1d252c">Mediana da razão calculado / ERICA por radionuclídeo e matriz</text>',
    ]
    for col, compartment in enumerate(compartments):
        x = left + col * cell_width
        parts.append(f'<text x="{x + cell_width / 2}" y="46" text-anchor="middle" font-size="11" fill="#1d252c">{escape(str(compartment.get("label") or ""))}</text>')
    for row_index, radionuclide in enumerate(radionuclides):
        y = top + row_index * cell_height
        parts.append(f'<text x="24" y="{y + 21}" font-size="11" fill="#1d252c">{escape(str(radionuclide))}</text>')
        for col, compartment in enumerate(compartments):
            x = left + col * cell_width
            cell = cells.get((radionuclide, compartment.get("key"))) or {}
            value = cell.get("median_ratio")
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_width - 8}" height="{cell_height - 6}" rx="3" fill="{color_for(value)}" stroke="#ffffff"/>'
                f'<text x="{x + (cell_width - 8) / 2}" y="{y + 19}" text-anchor="middle" font-size="10" fill="#1d252c">{escape(str(cell.get("median_ratio_text") or "—"))}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _chart_reading_html(text: str) -> str:
    return f'<p class="chart-reading">{escape(text)}</p>'


def _erica_scatter_reading(scope: dict[str, Any]) -> str:
    label = str(scope.get("scope_label") or "Escopo")
    generated_count = int(scope.get("generated_erica_count") or 0)
    generated_text = (
        f"Neste escopo há {generated_count} ponto(s) com ERICA gerado por stat_seed; por isso a leitura desses pontos é exploratória."
        if generated_count
        else "Quando houver ERICA gerado por stat_seed, a leitura desses pontos deve ser tratada como exploratória."
    )
    return (
        f"{label}: cada ponto representa um par data/radionuclídeo/matriz da razão calculado/ERICA. "
        "A linha vermelha em razão = 1 marca equivalência; pontos acima indicam concentração calculada maior que ERICA "
        f"e pontos abaixo indicam concentração calculada menor que ERICA. {generated_text}"
    )


def _total_activity_erica_graphs(review: dict[str, Any]) -> str:
    payload = review.get("erica_chart_payloads") or {}
    scopes = payload.get("scope_rows") or []
    if not scopes:
        return ""
    scatter_blocks = "".join(
        f'<article><h4>{escape(str(scope.get("scope_label") or ""))}</h4>{_chart_reading_html(_erica_scatter_reading(scope))}{_erica_ratio_scatter_svg(scope)}</article>'
        for scope in scopes
    )
    return f"""
<div class="explain-box">
  <p>{escape(payload.get('explanation') or '')}</p>
  <p>Os gráficos complementam os testes inferenciais: o boxplot mostra a distribuição das razões, a dispersão temporal mostra cada par por data e a linha vermelha em razão = 1 marca equivalência entre concentração calculada por fórmulas e ERICA Tool.</p>
</div>
<div class="chart-grid">
  <article>
    <h4>Boxplot por escopo</h4>
    {_chart_reading_html("O boxplot resume a razão calculado/ERICA por escopo. A caixa mostra os 50% centrais, a linha interna é a mediana, as hastes mostram mínimo e máximo, o ponto roxo marca o P95 e a escala log10 evita que valores extremos escondam diferenças próximas da equivalência. A linha vermelha em razão = 1 indica igualdade entre fórmula e ERICA; deslocamentos à direita indicam valores calculados maiores.")}
    {_erica_ratio_boxplot_svg(review)}
  </article>
  <article>
    <h4>Heatmap por radionuclídeo e matriz</h4>
    {_chart_reading_html("O heatmap mostra a mediana da razão calculado/ERICA para cada radionuclídeo e matriz. Células claras indicam medianas menores ou próximas de 1; células mais quentes indicam medianas acima de 1, ou seja, cálculo por fórmula maior que ERICA naquele cruzamento. Valores abaixo de 1 indicam cálculo menor que ERICA.")}
    {_erica_ratio_heatmap_svg(review)}
  </article>
  {scatter_blocks}
</div>
"""


def _total_activity_erica_table(review: dict[str, Any]) -> str:
    source_rows = list(review.get("erica_pair_rows") or [])
    grouped_rows = _group_by_radionuclide_matrix(source_rows)
    summary_rows = []
    detail_blocks = []
    for index, ((radionuclide, _compartment_key, compartment), group_rows) in enumerate(grouped_rows):
        calculated_values = _numeric_values(group_rows, "calculated_value")
        erica_values = _numeric_values(group_rows, "erica_value")
        ratio_values = _numeric_values(group_rows, "ratio")
        generated_count = sum(1 for item in group_rows if item.get("erica_generated"))
        summary_rows.append(
            "<tr>"
            f"<td>{escape(radionuclide)}</td>"
            f"<td>{escape(compartment)}</td>"
            f"<td>{len(group_rows)}</td>"
            f"<td>{_distinct_count(group_rows, 'date')}</td>"
            f"<td>{escape(group_rows[0].get('unit') or '')}</td>"
            f"<td>{escape(_mean_text(calculated_values))}</td>"
            f"<td>{escape(_mean_text(erica_values))}</td>"
            f"<td>{escape(_min_max_text(ratio_values))}</td>"
            f"<td>{generated_count}</td>"
            "</tr>"
        )
        detail_rows = []
        for item in group_rows:
            detail_rows.append(
                "<tr>"
                f"<td>{escape(item.get('date') or '')}</td>"
                f"<td>{escape(item.get('sample_id') or '')}</td>"
                f"<td>{escape(item.get('calculated_value_text') or '—')}</td>"
                f"<td>{escape(item.get('erica_value_text') or '—')}</td>"
                f"<td>{escape(item.get('ratio_text') or '—')}</td>"
                f"<td>{escape(item.get('erica_source') or '')}</td>"
                "</tr>"
            )
        detail_table = _tar_table(
            "tar-table--dense tar-table--detail",
            f"Detalhe calculado vs ERICA - {radionuclide} - {compartment}",
            "<tr><th>Data</th><th>Amostra</th><th>Calculado</th><th>ERICA</th><th>Calculado/ERICA</th><th>Origem ERICA</th></tr>",
            "".join(detail_rows),
            intro=(
                f"Esta tabela detalha os pares calculado/ERICA de {radionuclide} em {compartment}. "
                "Ela permite verificar, linha a linha, o valor calculado por fórmula, o valor ERICA usado e a razão entre os dois."
            ),
        )
        detail_blocks.append(
            _details_section(
                f"{radionuclide} - {compartment} ({len(group_rows)} pares)",
                detail_table,
                open_by_default=index == 0,
            )
        )
    summary_table = _tar_table(
        "tar-table--dense tar-table--summary",
        "Pares calculado vs ERICA Tool",
        "<tr><th>Radionuclídeo</th><th>Matriz</th><th>Pares</th><th>Datas</th><th>Unidade</th><th>Média calculada</th><th>Média ERICA</th><th>Razão mín. a máx.</th><th>Nº ERICA gerado</th></tr>",
        "".join(summary_rows),
        "Os pares detalhados ficam separados abaixo por radionuclídeo e matriz. A coluna 'Nº ERICA gerado' conta quantos pares usaram valor ERICA reproduzido por stat_seed; zero significa que todos os valores ERICA daquele grupo vieram da base disponível.",
        table_key="total_activity_erica",
    )
    details = "".join(detail_blocks)
    return f'{summary_table}<div class="tar-subsections"><h3>Detalhes dos pares ERICA</h3>{details}</div>'


def _total_activity_norm_table(review: dict[str, Any]) -> str:
    source_rows = list(review.get("norm_comparison_rows") or [])
    grouped_rows = _group_by_radionuclide_matrix(source_rows)
    summary_rows = []
    detail_blocks = []
    for index, ((radionuclide, _compartment_key, compartment), group_rows) in enumerate(grouped_rows):
        ratio_values = _numeric_values(group_rows, "ratio")
        references = ", ".join(sorted({str(item.get("reference") or "") for item in group_rows if item.get("reference")}))
        exceedance_count = sum(1 for item in group_rows if item.get("status") == "acima")
        summary_rows.append(
            "<tr>"
            f"<td>{escape(radionuclide)}</td>"
            f"<td>{escape(compartment)}</td>"
            f"<td>{escape(references or '—')}</td>"
            f"<td>{len(group_rows)}</td>"
            f"<td>{_distinct_count(group_rows, 'date')}</td>"
            f"<td>{escape(_min_max_text(ratio_values))}</td>"
            f"<td>{exceedance_count}</td>"
            "</tr>"
        )
        detail_rows = []
        for item in group_rows:
            detail_rows.append(
                "<tr>"
                f"<td>{escape(item.get('date') or '')}</td>"
                f"<td>{escape(item.get('sample_id') or '')}</td>"
                f"<td>{escape(item.get('reference') or '')}</td>"
                f"<td>{escape(item.get('value_text') or '—')}</td>"
                f"<td>{escape(item.get('reference_value_text') or '—')}</td>"
                f"<td>{escape(item.get('ratio_text') or '—')}</td>"
                f'<td><span class="pill {_status_class(str(item.get("status") or ""))}">{escape(item.get("status") or "—")}</span></td>'
                "</tr>"
            )
        detail_table = _tar_table(
            "tar-table--dense tar-table--detail",
            f"Detalhe normativo - {radionuclide} - {compartment}",
            "<tr><th>Data</th><th>Amostra</th><th>Referência</th><th>Valor</th><th>Referência</th><th>Razão</th><th>Status</th></tr>",
            "".join(detail_rows),
            intro=(
                f"Esta tabela detalha a comparação normativa de {radionuclide} em {compartment}. "
                "Cada linha compara o valor calculado com Report Level ou LLD e registra a razão e o status correspondente."
            ),
        )
        detail_blocks.append(
            _details_section(
                f"{radionuclide} - {compartment} ({len(group_rows)} comparações)",
                detail_table,
                open_by_default=index == 0,
            )
        )
    summary_table = _tar_table(
        "tar-table--dense tar-table--summary",
        "Comparação com Report Level e LLD por linha completa",
        "<tr><th>Radionuclídeo</th><th>Matriz</th><th>Referências</th><th>Comparações</th><th>Datas</th><th>Razão mín. a máx.</th><th>Acima</th></tr>",
        "".join(summary_rows),
        "Os detalhes ficam separados abaixo por radionuclídeo e matriz. LLD é referência de detecção e não limite de ação.",
        table_key="total_activity_norms",
    )
    details = "".join(detail_blocks)
    return f'{summary_table}<div class="tar-subsections"><h3>Detalhes normativos</h3>{details}</div>'


def _total_activity_inferential_table(review: dict[str, Any]) -> str:
    source_rows = list(review.get("inferential_rows") or [])
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in source_rows:
        group_type = str(item.get("group_type") or "Radionuclídeo-matriz")
        grouped.setdefault((str(item.get("comparison_type") or ""), group_type), []).append(item)
    group_order = {"Geral": 0, "Matriz": 1, "Radionuclídeo": 2, "Radionuclídeo-matriz": 3}
    grouped_rows = sorted(grouped.items(), key=lambda item: (item[0][0], group_order.get(item[0][1], 9), item[0][1]))
    summary_rows = []
    detail_blocks = []
    for index, ((comparison_type, group_type), group_rows) in enumerate(grouped_rows):
        n_values = [int(row.get("n") or 0) for row in group_rows if row.get("n")]
        p_values = _numeric_values(group_rows, "p_value")
        tests = ", ".join(sorted({str(row.get("test_label") or "") for row in group_rows if row.get("test_label")}))
        generated_count = sum(int(row.get("generated_erica_count") or 0) for row in group_rows)
        n_text = f"{min(n_values)} a {max(n_values)}" if n_values else "—"
        p_text = _format_sci(min(p_values)) if p_values else "—"
        summary_rows.append(
            "<tr>"
            f"<td>{escape(comparison_type)}</td>"
            f"<td>{escape(group_type)}</td>"
            f"<td>{len(group_rows)}</td>"
            f"<td>{escape(n_text)}</td>"
            f"<td>{escape(tests or '—')}</td>"
            f"<td>{escape(p_text)}</td>"
            f"<td>{generated_count}</td>"
            "</tr>"
        )
        detail_rows = []
        for item in group_rows:
            summary_value = item.get("median_ratio_text") or item.get("p95_ratio_text") or "—"
            detail_rows.append(
                "<tr>"
                f"<td>{escape(item.get('scope') or '')}</td>"
                f"<td>{escape(str(item.get('n') or '—'))}</td>"
                f"<td>{escape(item.get('reference') or '—')}</td>"
                f"<td>{escape(item.get('shapiro_p_text') or '—')}</td>"
                f"<td>{escape(item.get('test_label') or '—')}</td>"
                f"<td>{escape(item.get('p_value_text') or '—')}</td>"
                f"<td>{escape(summary_value)}</td>"
                f"<td>{escape(item.get('exceedance_rate_text') or '—')}</td>"
                f"<td>{escape(item.get('generated_erica_count_text') or '0')}</td>"
                f"<td>{escape(item.get('conclusion') or item.get('reason') or '')}</td>"
                "</tr>"
            )
        detail_table = _tar_table(
            "tar-table--dense tar-table--detail",
            f"Detalhe inferencial - {comparison_type} - {group_type}",
            "<tr><th>Escopo</th><th>n</th><th>Referência</th><th>Shapiro-Wilk</th><th>Teste</th><th>p-value</th><th>Resumo razão</th><th>Ultrapassagem</th><th>Nº ERICA gerado</th><th>Conclusão</th></tr>",
            "".join(detail_rows),
            intro=(
                f"Esta tabela detalha os testes inferenciais do grupo {group_type} para a comparação {comparison_type}. "
                "Ela mostra o escopo testado, o n válido, a normalidade, o teste selecionado, o p-value e a conclusão exploratória."
            ),
        )
        detail_blocks.append(
            _details_section(
                f"{comparison_type} - {group_type} ({len(group_rows)} testes)",
                detail_table,
                open_by_default=index == 0,
            )
        )
    summary_table = _tar_table(
        "tar-table--dense tar-table--summary",
        "Testes inferenciais das janelas mínimas",
        "<tr><th>Comparação</th><th>Grupo</th><th>Testes</th><th>n nos testes</th><th>Procedimentos</th><th>Menor p-value</th><th>Nº ERICA gerado</th></tr>",
        "".join(summary_rows),
        "Os p-values e conclusões ficam separados abaixo por grupo. Comparações com LLD são tratadas como referência de detecção. A coluna 'Nº ERICA gerado' conta pares com valor ERICA reproduzido por stat_seed, que entram com ressalva exploratória.",
        table_key="total_activity_inferential",
    )
    details = "".join(detail_blocks)
    return f'{summary_table}<div class="tar-subsections"><h3>Detalhes inferenciais</h3>{details}</div>'


def _academic_methodology_panel(summary: dict[str, Any]) -> str:
    scenario = summary.get("scenario") or {}
    review = scenario.get("total_activity_review") or {}
    source_text = ""
    if review:
        source_text = (
            f" As fontes usadas são: A-TAR em {escape(str(review.get('source_total_workbook_path') or ''))}, "
            f"aba {escape(str(review.get('source_total_sheet') or ''))}; composição radionuclídica em "
            f"{escape(str(review.get('source_radionuclide_workbook_path') or ''))}, "
            f"aba {escape(str(review.get('source_radionuclide_sheet') or ''))}; e constantes/fatores da planilha TAR no cenário selecionado."
        )
    return f"""
<section class="panel report-block" id="metodologia">
  <h2>Metodologia</h2>
  <article class="report-block-child" id="metodologia-fontes">
    <h3>Fontes e cruzamento</h3>
    <p>O relatório cruza a atividade total do tanque com a composição radionuclídica disponível para datas equivalentes ou próximas. A atividade total define a intensidade do evento avaliado; a composição radionuclídica define a participação de cada radionuclídeo na atividade total usada nos cálculos.{source_text}</p>
  </article>
  <article class="report-block-child" id="metodologia-selecao">
    <h3>Seleção temporal e censura</h3>
    <p>A análise audita as maiores atividades totais do tanque e, para o cálculo principal, seleciona janelas mínimas que concentrem pelo menos oito radionuclídeos diferentes na data mais próxima possível. Entradas marcadas como &lt; MDA&gt; contam como informação censurada para completude, mas não entram como valor numérico no denominador das frações.</p>
  </article>
  <article class="report-block-child" id="metodologia-formulas">
    <h3>Fórmulas de concentração</h3>
    <p>Para cada linha selecionada, calcula-se a fração Si do radionuclídeo, a atividade Ai, a concentração na água pela vazão do cenário e as incorporações em peixes, invertebrados e sedimento pelos fatores registrados na planilha TAR. As constantes de meia-vida, decaimento, bioacumulação, Kd, fator sedimentar e tempo de acumulação são documentadas antes dos resultados por matriz.</p>
  </article>
  <article class="report-block-child" id="metodologia-erica">
    <h3>ERICA Tool</h3>
    <p>Os valores calculados por fórmula são pareados com valores do ERICA Tool quando disponíveis. Pares ausentes recebem valores reprodutíveis por <code>stat_seed</code>, marcados com asterisco, para permitir comparação exploratória sem confundir esses pontos com saída regulatória definitiva do ERICA.</p>
  </article>
  <article class="report-block-child" id="metodologia-estatistica">
    <h3>Estatística descritiva e inferencial</h3>
    <p>A estatística descritiva resume médias, medianas, P95 e distribuições gráficas da razão calculado/ERICA. A inferência usa log(calculado/ERICA) em testes pareados e log(valor/referência) para Report Level e LLD, aplicando Shapiro-Wilk e então teste t ou Wilcoxon conforme normalidade. Report Level é critério de notificação; LLD é referência de detecção.</p>
  </article>
</section>
"""


def _total_activity_review_panel(summary: dict[str, Any]) -> str:
    review = (summary.get("scenario") or {}).get("total_activity_review") or {}
    if not review:
        return ""
    return f"""
<section class="panel report-block" id="atividade-total">
  <h2>Resultados da atividade total e composição radionuclídica</h2>
  <article class="report-block-child" id="atividade-total-analise-dados">
    <h3>Apresentação dos dados</h3>
    <p>{escape(review.get('narrative_text') or '')}</p>
    <p class="table-note">Fonte A-TAR: {escape(str(review.get('source_total_workbook_path') or ''))}, aba {escape(str(review.get('source_total_sheet') or ''))}. Fonte radionuclídeos: {escape(str(review.get('source_radionuclide_workbook_path') or ''))}, aba {escape(str(review.get('source_radionuclide_sheet') or ''))}.</p>
    <div class="cards sensitivity-cards">{_total_activity_review_cards(review)}</div>
    <p>Este bloco audita as maiores atividades totais do tanque, identifica completude radionuclídica e seleciona as janelas mínimas que concentram pelo menos oito radionuclídeos diferentes na data mais próxima possível.</p>
    {_total_activity_top15_table(review)}
    {_total_activity_complete_table(review)}
  </article>
  <article class="report-block-child" id="atividade-total-formulas">
    <h3>Cálculo das concentrações por fórmulas</h3>
    <p>Este bloco documenta as equações aplicadas aos dados completos e as constantes lidas da aba de cenário selecionada, incluindo vazão, meia-vida, fatores de bioacumulação, Kd, fator sedimentar e tempo de acumulação.</p>
    {_total_activity_formula_table(review)}
    {_total_activity_constants_table(review)}
    <p>Este bloco apresenta água, sedimento, peixes e invertebrados em resumos por radionuclídeo e matriz, com os detalhes separados em blocos recolhíveis.</p>
    {_total_activity_matrix_table(review)}
  </article>
  <article class="report-block-child" id="atividade-total-erica">
    <h3>Comparação atividade calculada x ERICA Tool</h3>
    <p>Este bloco pareia cada atividade calculada com o respectivo valor ERICA disponível ou gerado de forma reprodutível, mantendo a marcação dos valores com asterisco para leitura exploratória.</p>
    {_total_activity_erica_table(review)}
  </article>
  <article class="report-block-child" id="atividade-total-descritiva">
    <h3>Estatística descritiva</h3>
    <p>Este bloco resume a distribuição da razão calculado/ERICA em boxplots, dispersões temporais e heatmap por radionuclídeo e matriz, usando os mesmos pares apresentados na seção anterior.</p>
    {_total_activity_erica_graphs(review)}
  </article>
  <article class="report-block-child" id="atividade-total-inferencia">
    <h3>Estatística inferencial</h3>
    <p>Este bloco reúne os testes sobre log(calculado/ERICA) e log(valor/referência), com Shapiro-Wilk, teste t ou Wilcoxon conforme normalidade, frequências de ultrapassagem e ressalvas metodológicas.</p>
    {_total_activity_inferential_table(review)}
  </article>
  <article class="report-block-child" id="atividade-total-normas">
    <h3>Comparação com Report Level e LLD</h3>
    <p>Este bloco separa a leitura normativa: Report Level é tratado como critério de notificação e LLD como referência de detecção, não como limite de ação.</p>
    {_total_activity_norm_table(review)}
  </article>
</section>
"""


def _statistical_comparison_panel(summary: dict[str, Any]) -> str:
    statistical = (summary.get("scenario") or {}).get("statistical_comparison") or {}
    if not statistical:
        return ""
    descriptive_html = _stat_descriptive_table(statistical) if statistical.get("descriptive_rows") else ""
    paired_html = _stat_paired_table(statistical) if statistical.get("paired_comparison_rows") else ""
    return f"""
<section class="panel report-block" id="estatistica-geral">
  <h2>Estatística calculado vs ERICA vs norma</h2>
  <article class="report-block-child" id="estatistica-metodologia">
    <h3>Metodologia estatística complementar</h3>
    <p>{escape(statistical.get('narrative_text') or '')}</p>
    <p class="table-note">Esta seção não usa replicações aleatórias. A norma é referência fixa; os valores do ERICA Tool são estimativas para visualização até substituição por saídas reais.</p>
    <p>A estatística descritiva resume dispersão, P95 e CV dos valores calculados e estimados por compartimento. A inferência contra norma fica na seção dos dados reais do TAR - Afluente.</p>
  </article>
  <article class="report-block-child" id="estatistica-fontes">
    <h3>Fontes comparadas: cálculo, ERICA e normas</h3>
    {_stat_source_rows_table(statistical, "calculated_rows", "Dados calculados por fórmulas de transporte/incorporação", "A planilha TAR fornece concentrações calculadas por fórmulas e modelos de transporte para água, peixe, invertebrado e sedimento.")}
    {_stat_source_rows_table(statistical, "erica_rows", "Dados simulados pelo ERICA Tool", "O ERICA Tool foi usado como estimativa de dose/risco ambiental até o Nível 2. Água foi convertida de Bq/L para Bq/m³ quando necessário.")}
    {_stat_source_rows_table(statistical, "norm_rows", "Normas: Report Level e LLD", "Report Level e LLD são referências normativas fixas e não entram como amostras aleatórias.")}
  </article>
  <article class="report-block-child" id="estatistica-descritiva">
    <h3>Estatística descritiva</h3>
    {descriptive_html}
  </article>
  <article class="report-block-child" id="estatistica-erica-pareada">
    <h3>Comparação pareada com ERICA Tool</h3>
    {paired_html}
  </article>
</section>
"""


def _base_html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    @page {{ size: A4; margin: 1.8cm 1.6cm 1.8cm 1.8cm; }}
    :root {{
      color-scheme: light;
      --ink: #1d252c;
      --muted: #52616a;
      --line: #d6ddd9;
      --line-strong: #3f474d;
      --soft: #f7fbf9;
      --accent: #2d8577;
      --report-font-family: "Times New Roman", Times, serif;
      --report-body-size: 12pt;
      --report-table-font-family: "Times New Roman", Times, serif;
      --report-table-size: 9pt;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: var(--report-font-family); color: var(--ink); background: #e8edf0; font-size: var(--report-body-size); line-height: 1.42; }}
    main.report-pages {{ max-width: 1020px; margin: 0 auto; padding: 28px 20px 48px; }}
    .tar-header, .panel {{ width: 210mm; max-width: calc(100vw - 32px); margin: 0 auto 22px; background: #fff; border: 1px solid #cbd4d8; border-radius: 2px; padding: 1.8cm 1.6cm 1.8cm 1.8cm; box-shadow: 0 14px 36px rgba(31, 47, 55, 0.14); }}
    .tar-header {{ display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; }}
    h1, h2, h3, h4 {{ margin: 0 0 10px; font-family: var(--report-font-family); letter-spacing: 0; }}
    h1 {{ font-size: 20pt; line-height: 1.2; }}
    h2 {{ margin-top: 8px; font-size: 15pt; line-height: 1.25; }}
    h3 {{ margin-top: 18px; font-size: 12.5pt; line-height: 1.25; }}
    p {{ line-height: 1.42; margin: 8px 0; }}
    .panel p, .article-text p, .explain-text, .table-note, .column-notes li, .toc-list p, .toc-children span {{ text-align: justify; }}
    section[id], article[id] {{ scroll-margin-top: 18px; }}
    .scenario-tabs {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .scenario-tab {{ display: inline-flex; border: 1px solid var(--line); border-radius: 999px; padding: 7px 11px; color: #22675f; text-decoration: none; background: #fff; font-size: 10.5pt; }}
    .scenario-tab.selected {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ background: var(--soft); border: 1px solid var(--line); border-radius: 2px; padding: 12px; }}
    .card strong {{ display: block; font-size: 16pt; margin-top: 4px; }}
    .muted-text {{ color: var(--muted); }}
    .toc-panel p {{ color: #1d252c; }}
    .toc-list {{ margin: 12px 0 0; padding-left: 0; list-style: none; display: grid; gap: 12px; counter-reset: toc; }}
    .toc-list > li {{ border-top: 1px solid var(--line); padding-top: 10px; }}
    .toc-title {{ display: inline-flex; align-items: baseline; gap: 8px; color: #1d252c; font-weight: 700; text-decoration: none; }}
    .toc-title:hover, .toc-children a:hover {{ text-decoration: underline; }}
    .toc-number {{ display: inline-flex; justify-content: center; min-width: 22px; color: #1d252c; font-family: var(--report-font-family); font-weight: 700; }}
    .toc-list p {{ margin: 4px 0 0 30px; font-size: 10.5pt; }}
    .toc-children {{ margin: 8px 0 0 30px; padding-left: 0; list-style: none; display: grid; gap: 5px; }}
    .toc-children li {{ padding-left: 2px; }}
    .toc-children a {{ display: inline-flex; align-items: baseline; gap: 8px; color: #1d252c; font-weight: 700; text-decoration: none; }}
    .toc-children span {{ display: block; color: #1d252c; font-size: 10pt; line-height: 1.35; }}
    .report-block-child {{ border-top: 1px solid var(--line); margin-top: 18px; padding-top: 14px; }}
    .report-block-child:first-of-type {{ border-top: 0; margin-top: 8px; padding-top: 0; }}
    .table-scroll {{ max-width: 100%; overflow-x: auto; margin: 10px 0 0; }}
    .table-scroll--fit {{ overflow-x: visible; }}
    .tar-table {{ width: auto; max-width: 100%; margin: 0 auto; border-collapse: collapse; table-layout: auto; border: 1.25px solid var(--line-strong); background: #fff; }}
    .tar-table caption {{ caption-side: top; text-align: center; font-weight: 700; color: #1d252c; padding: 0 0 7px; font-size: 11pt; line-height: 1.3; }}
    .tar-table th, .tar-table td {{ border: 1px dotted #5a6369; padding: 6px 9px; text-align: center; vertical-align: middle; font-size: var(--report-table-size); font-family: var(--report-table-font-family); line-height: 1.24; white-space: normal; overflow-wrap: break-word; word-wrap: break-word; word-break: normal; }}
    .tar-table th {{ background: #f8f8f8; color: #1d252c; font-weight: 700; border-bottom: 1.6px solid var(--line-strong); }}
    .tar-table thead tr:first-child th {{ border-top: 1.25px solid var(--line-strong); }}
    .tar-table tbody tr:first-child td {{ border-top: 1.6px solid var(--line-strong); }}
    .tar-table tbody tr:last-child td {{ border-bottom: 1.25px solid var(--line-strong); }}
    .tar-table tr > :first-child {{ border-left: 1.25px solid var(--line-strong); }}
    .tar-table tr > :last-child {{ border-right: 1.25px solid var(--line-strong); }}
    .tar-table th span {{ display: block; color: var(--muted); font-weight: normal; font-size: 8.5pt; }}
    .tar-table--dense th, .tar-table--dense td {{ font-size: var(--report-table-size); }}
    .tar-table--wide {{ width: auto; max-width: 100%; table-layout: auto; }}
    .tar-table--fit {{ width: 100%; max-width: 100%; table-layout: fixed; }}
    .tar-table--fit th, .tar-table--fit td {{ padding: 3px 4px; font-size: 7pt; line-height: 1.1; white-space: normal; overflow-wrap: anywhere; word-wrap: break-word; word-break: normal; }}
    .tar-table--fit caption {{ font-size: 10pt; }}
    .tar-table--fit .pill {{ max-width: 100%; white-space: normal; overflow-wrap: anywhere; justify-content: center; line-height: 1.05; padding: 2px 5px; }}
    .tar-table--summary {{ margin-bottom: 8px; }}
    .tar-table--detail caption {{ font-size: 10pt; }}
    .pill {{ display: inline-flex; border-radius: 999px; padding: 2px 8px; font-size: 9pt; border: 1px solid var(--line); }}
    .pill.good {{ background: #edf8f0; color: #1f6b3a; border-color: #bfdfc8; }}
    .pill.bad {{ background: #fff0f0; color: #9a2424; border-color: #e6bbbb; }}
    .pill.muted {{ background: #f4f6f7; color: #607782; }}
    .explain-text {{ color: #405862; font-size: 10.5pt; line-height: 1.45; margin: 10px 0 8px; }}
    .explain-box {{ border-left: 4px solid var(--accent); background: #f7fafb; padding: 10px 12px; margin: 12px 0; }}
    .explain-box p {{ color: #405862; font-size: 10.5pt; line-height: 1.45; margin: 6px 0; }}
    .column-notes-block {{ border-left: 4px solid var(--line); background: #f7fafb; padding: 10px 12px; margin: 10px 0; color: #405862; font-size: 10.5pt; }}
    .column-notes-block strong {{ display: block; color: #203f49; margin-bottom: 4px; }}
    .column-notes {{ margin: 4px 0 0 20px; padding: 0; }}
    .column-notes li {{ margin: 3px 0; line-height: 1.4; }}
    .table-note {{ margin: 6px 0 0; color: var(--muted); font-size: 10pt; line-height: 1.4; }}
    .table-legend {{ margin: 8px 0 12px; }}
    .tar-subsections {{ margin-top: 16px; display: grid; gap: 10px; }}
    .tar-subsection {{ border: 1px solid var(--line); background: #fbfdfc; padding: 0; }}
    .tar-subsection summary {{ cursor: pointer; padding: 10px 12px; font-family: var(--report-table-font-family); font-size: 10pt; font-weight: 700; color: #203f49; }}
    .tar-subsection[open] summary {{ border-bottom: 1px solid var(--line); background: #f3f7f5; }}
    .tar-subsection .table-scroll {{ padding: 0 12px 12px; }}
    .tar-chart {{ width: 100%; max-width: 520px; display: block; margin-top: 10px; }}
    .tar-chart text {{ font-family: var(--report-font-family); }}
    .tar-chart--wide {{ max-width: 100%; }}
    .sensitivity-chart-grid {{ display: grid; gap: 14px; margin-top: 12px; }}
    .sensitivity-chart-grid article {{ border: 1px solid var(--line); border-radius: 2px; padding: 12px; overflow-x: auto; }}
    .sensitivity-cards {{ margin: 12px 0; }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }}
    .button {{ display: inline-flex; padding: 8px 12px; border-radius: 2px; background: var(--accent); color: #fff; text-decoration: none; }}
    .cover-title {{ margin: 22px 0 18px; font-size: 19pt; line-height: 1.35; text-align: center; text-transform: uppercase; }}
    .cover-label {{ display: block; color: #52616a; font-size: 10pt; text-transform: uppercase; letter-spacing: .06em; text-align: center; }}
    .cover-meta {{ border: 1px solid var(--line); background: #f7fbf9; padding: 12px 14px; margin-top: 18px; font-size: 10.5pt; }}
    .chart-grid {{ display: grid; gap: 14px; margin-top: 12px; }}
    .chart-grid article {{ border: 1px solid var(--line); border-radius: 2px; padding: 12px; overflow-x: visible; background: #fff; }}
    .chart-grid h4 {{ margin-top: 0; font-size: 11pt; }}
    .chart-reading {{ color: #405862; font-size: 10pt; line-height: 1.38; margin: 6px 0 10px; text-align: justify; }}
    .article-text h2 {{ margin-top: 20px; }}
    .article-text p {{ text-align: justify; }}
    .article-source {{ font-size: 12px; color: var(--muted); margin-bottom: 12px; }}
    @media (max-width: 760px) {{
      main.report-pages {{ padding: 12px; }}
      .tar-header, .panel {{ display: block; padding: 20px 16px; }}
      .scenario-tabs {{ margin-top: 12px; }}
    }}
    @media print {{
      body {{ background: #fff; margin: 0; }}
      main.report-pages {{ max-width: none; padding: 0; }}
      .tar-header, .panel {{ box-shadow: none; border: 0; padding: 0; margin: 0 0 22px; }}
      .actions, .scenario-tabs {{ display: none; }}
      .table-scroll {{ overflow: visible; }}
      .tar-table, .tar-table--wide {{ width: auto !important; max-width: 100% !important; table-layout: auto !important; }}
      .tar-table--fit {{ width: 100% !important; max-width: 100% !important; table-layout: fixed !important; }}
      .tar-table--fit th, .tar-table--fit td {{ white-space: normal !important; overflow-wrap: break-word !important; word-wrap: break-word !important; word-break: normal !important; }}
      .tar-subsection {{ break-inside: avoid-page; page-break-inside: avoid; }}
    }}
  </style>
</head>
<body><main class="report-pages">{body}</main></body>
</html>"""


def _summary_intro(summary: dict[str, Any]) -> str:
    scenario = summary["scenario"]
    totals = scenario["totals"]
    if scenario.get("is_hypothetical"):
        return (
            f"<p>A avaliação TAR considera o cenário hipotético, com n = {scenario['measurement_count']} medições sintéticas "
            f"de espectrometria gama por radionuclídeo da água do TAR. Cada medição gerou uma simulação dos compartimentos ambientais. "
            f"Os valores exibidos nas tabelas de concentração correspondem ao percentil 95 das simulações. "
            f"A concentração total P95 na água do mar foi {_format_sci(totals.get('total_water_concentration_bq_m3'))} Bq/m³.</p>"
        )
    exceedance_text = (
        "Os valores com Report Level disponível ficaram abaixo dos níveis de notificação cadastrados."
        if not scenario["has_reference_exceedance"]
        else "Há valores acima de Report Level que exigem conferência técnica."
    )
    return (
        f"<p>A avaliação TAR considera o cenário {escape(scenario['label'])}, com "
        f"n = {scenario['radionuclide_count']} radionuclídeos calculados. "
        f"A concentração total na água do mar foi {_format_sci(totals.get('total_water_concentration_bq_m3'))} Bq/m³, "
        f"com atividade de {_format_sci(totals.get('activity_bq_year'))} Bq/ano. {escape(exceedance_text)}</p>"
    )


def _activity_total_toc_children() -> list[dict[str, str]]:
    return [
        _toc_child("atividade-total-analise-dados", "Apresentação dos dados", "Top 15, completude e janelas mínimas de datas próximas."),
        _toc_child("atividade-total-formulas", "Concentrações por fórmulas", "Si, Ai, constantes, fatores e resultados por matriz ambiental."),
        _toc_child("atividade-total-erica", "Calculado x ERICA", "Pares calculados versus ERICA Tool, incluindo valores gerados com asterisco."),
        _toc_child("atividade-total-descritiva", "Estatística descritiva", "Boxplots, dispersão temporal, heatmap, médias, medianas e P95."),
        _toc_child("atividade-total-inferencia", "Estatística inferencial", "Shapiro-Wilk, teste t ou Wilcoxon e frequências de ultrapassagem."),
        _toc_child("atividade-total-normas", "Report Level e LLD", "Comparação normativa, com LLD tratado como referência de detecção."),
    ]


def _methodology_toc_children() -> list[dict[str, str]]:
    return [
        _toc_child("metodologia-fontes", "Fontes e cruzamento", "Planilhas usadas e lógica de associação entre A-TAR e radionuclídeos."),
        _toc_child("metodologia-selecao", "Seleção temporal e censura", "Janelas próximas e tratamento de resultados < MDA>."),
        _toc_child("metodologia-formulas", "Fórmulas de concentração", "Frações, atividades, matrizes ambientais e constantes."),
        _toc_child("metodologia-erica", "ERICA Tool", "Pareamento calculado x ERICA e valores gerados por stat_seed."),
        _toc_child("metodologia-estatistica", "Estatística descritiva e inferencial", "Resumo gráfico, Shapiro-Wilk, teste t, Wilcoxon, Report Level e LLD."),
    ]


def _empirical_toc_children() -> list[dict[str, str]]:
    return [
        _toc_child("dados-reais-entrada", "Entrada das amostras", "Afluente, efluente, censura < MDA> e radionuclídeos observados."),
        _toc_child("dados-reais-calculos", "Cálculos por fórmula", "Aplicação da lógica TAR aos dados reais por compartimento."),
        _toc_child("dados-reais-inferencia", "Inferência real", "Testes contra Report Level usando amostras reais do TAR - Afluente."),
    ]


def _statistical_toc_children() -> list[dict[str, str]]:
    return [
        _toc_child("estatistica-metodologia", "Metodologia estatística", "Premissas da comparação calculado, ERICA e normas."),
        _toc_child("estatistica-fontes", "Fontes comparadas", "Dados calculados, ERICA Tool, Report Level e LLD."),
        _toc_child("estatistica-descritiva", "Descritiva", "Dispersão, P95, CV e resumo dos valores."),
        _toc_child("estatistica-erica-pareada", "Pareamento ERICA", "Comparação pareada entre cálculo por fórmula e ERICA Tool."),
    ]


def _dashboard_toc_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    scenario = summary.get("scenario") or {}
    items = [
        _toc_item("introducao", "Introdução e escopo", "Cenário selecionado, radionuclídeos avaliados e atalhos de exportação."),
    ]
    if scenario.get("total_activity_review"):
        items.extend(
            [
                _toc_item("metodologia", "Metodologia", "Fontes, cruzamento, seleção temporal, fórmulas, ERICA Tool e testes.", _methodology_toc_children()),
                _toc_item("atividade-total-analise-dados", "Apresentação dos dados", "Top 15, completude e janelas mínimas de datas próximas."),
                _toc_item("atividade-total-formulas", "Concentrações por fórmulas", "Constantes, fatores, fórmulas e resultados por matriz ambiental."),
                _toc_item("atividade-total-erica", "Calculado x ERICA", "Pares calculados versus ERICA Tool, incluindo valores gerados com asterisco."),
                _toc_item("atividade-total-descritiva", "Estatística descritiva", "Boxplots, dispersão temporal, heatmap, médias, medianas e P95."),
                _toc_item("atividade-total-inferencia", "Estatística inferencial", "Shapiro-Wilk, teste t ou Wilcoxon, p-values e ressalvas."),
                _toc_item("atividade-total-normas", "Report Level e LLD", "Report Level como notificação; LLD como referência de detecção."),
            ]
        )
    else:
        items.extend(
            [
                _toc_item("referencias-disponiveis", "Referências disponíveis", "Disponibilidade de Report Level e LLD por matriz ambiental."),
                _toc_item("concentracoes-cenario", "Concentrações calculadas", "Resultados do cenário selecionado."),
                _toc_item("comparacao-normativa-cenario", "Comparação normativa inicial", "Comparação direta com Report Level e LLD da planilha TAR."),
            ]
        )
    if scenario.get("is_hypothetical"):
        items.extend(
            [
                _toc_item("hipotetico-medicoes", "Medições sintéticas", "Série hipotética de espectrometria gama por radionuclídeo."),
                _toc_item("hipotetico-inferencia", "Inferência do cenário hipotético", "Teste estatístico das simulações contra Report Level."),
            ]
        )
    if scenario.get("empirical_activity_statistics"):
        items.append(
            _toc_item("dados-reais-tar", "Dados reais TAR", "Organização das amostras reais e inferência contra Report Level.", _empirical_toc_children())
        )
    if scenario.get("statistical_comparison"):
        items.append(
            _toc_item(
                "estatistica-geral",
                "Estatística complementar calculado x ERICA x norma",
                "Resumo estatístico complementar com dados calculados, ERICA Tool e referências fixas.",
                _statistical_toc_children(),
            )
        )
    items.append(_toc_item("suficiencia-estatistica", "Discussão e conclusão", "Critérios mínimos, limitações, suficiência estatística e interpretação final."))
    return items


def _report_toc_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    scenario = summary.get("scenario") or {}
    items = [
        _toc_item("resumo", "Introdução e escopo", "Escopo do relatório, cenário selecionado e conjunto de radionuclídeos."),
    ]
    if scenario.get("total_activity_review"):
        items.extend(
            [
                _toc_item("metodologia", "Metodologia", "Fontes, cruzamento, seleção temporal, fórmulas, ERICA Tool e testes.", _methodology_toc_children()),
                _toc_item("atividade-total-analise-dados", "Apresentação dos dados", "Top 15, completude e janelas mínimas de datas próximas."),
                _toc_item("atividade-total-formulas", "Concentrações por fórmulas", "Constantes, fatores, fórmulas e resultados por matriz ambiental."),
                _toc_item("atividade-total-erica", "Calculado x ERICA", "Pares calculados versus ERICA Tool, incluindo valores gerados com asterisco."),
                _toc_item("atividade-total-descritiva", "Estatística descritiva", "Boxplots, dispersão temporal, heatmap, médias, medianas e P95."),
                _toc_item("atividade-total-inferencia", "Estatística inferencial", "Shapiro-Wilk, teste t ou Wilcoxon, p-values e ressalvas."),
                _toc_item("atividade-total-normas", "Report Level e LLD", "Report Level como notificação; LLD como referência de detecção."),
            ]
        )
    if scenario.get("empirical_activity_statistics"):
        items.append(
            _toc_item("dados-reais-tar", "Dados reais TAR", "Amostras reais, cálculos por fórmula e inferência contra Report Level.", _empirical_toc_children())
        )
    if not scenario.get("total_activity_review"):
        items.append(_toc_item("comparacao-normativa-cenario", "Comparação com Report Level e LLD", "Leitura normativa inicial antes da auditoria detalhada por A-TAR."))
    if scenario.get("statistical_comparison"):
        items.append(
            _toc_item(
                "estatistica-geral",
                "Estatística complementar",
                "Dados calculados, ERICA Tool, normas fixas, descritiva e pareamento.",
                _statistical_toc_children(),
            )
        )
    items.extend(
        [
            _toc_item("suficiencia-estatistica", "Discussão e conclusão", "Limitações e critérios mínimos para conclusão inferencial."),
            _toc_item("exportacao", "Exportação", "Atalhos para DOCX, PDF e ARTIGO BETA."),
        ]
    )
    return items


def _article_toc_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        _toc_item("texto-artigo", "Introdução e texto base", "Base editorial importada do arquivo local do Artigo TAR corrigido."),
    ]
    scenario = summary.get("scenario") or {}
    if scenario.get("total_activity_review"):
        items.extend(
            [
                _toc_item("metodologia", "Metodologia", "Fontes, cruzamento, seleção temporal, fórmulas, ERICA Tool e testes.", _methodology_toc_children()),
                _toc_item("atividade-total", "Resultados da atividade total", "Apresentação dos dados, fórmulas, ERICA, descritiva, inferência e normas.", _activity_total_toc_children()),
            ]
        )
    items.extend(
        [
            _toc_item("dados-relatorio", "Dados do relatório TAR", "Resumo técnico incorporado ao artigo beta."),
            _toc_item("comparacao-normativa-cenario", "Comparação normativa", "Report Level e LLD como referências fixas."),
        ]
    )
    if scenario.get("empirical_activity_statistics"):
        items.append(
            _toc_item("dados-reais-tar", "Dados reais TAR", "Amostras reais e inferência contra Report Level.", _empirical_toc_children())
        )
    if scenario.get("statistical_comparison"):
        items.append(
            _toc_item("estatistica-geral", "Estatística complementar", "Comparação calculado x ERICA x norma e descritiva.", _statistical_toc_children())
        )
    items.extend(
        [
            _toc_item("suficiencia-estatistica", "Suficiência estatística", "Leitura das limitações estatísticas do conjunto."),
            _toc_item("acoes", "Ações", "Atalhos para retornar ao TAR ou abrir o relatório."),
        ]
    )
    return items


def render_tar_dashboard_html(summary: dict[str, Any]) -> str:
    scenario = summary["scenario"]
    assessment = summary["inferential_assessment"]
    inferential_label = "dados reais" if assessment.get("applicable") else "limitada"
    cards = [
        ("Radionuclídeos", str(scenario["radionuclide_count"])),
        ("Cenário", scenario["label"]),
        ("Report Level", "0 acima" if not scenario["has_reference_exceedance"] else f"{len(scenario['exceedances'])} acima"),
        ("Inferência", inferential_label),
    ]
    card_html = "".join(f'<div class="card"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>' for label, value in cards)
    legacy_reference_sections = ""
    if not scenario.get("total_activity_review"):
        legacy_reference_sections = f"""
<section class="panel report-block" id="referencias-disponiveis">
  <h2>Referências disponíveis</h2>
  <p>Água e peixe têm 4 referências disponíveis, sedimento tem 1 referência e invertebrado não tem referência cadastrada na planilha. O Report Level foi tratado como critério de notificação; o LLD permanece como referência de detecção.</p>
  {_reference_svg(summary)}
  {_reference_counts_table(summary)}
</section>
<section class="panel report-block" id="concentracoes-cenario">
  <h2>Concentrações calculadas</h2>
  {_concentration_table(summary)}
</section>
<section class="panel report-block" id="comparacao-normativa-cenario">
  <h2>Comparação com Report Level e LLD</h2>
  {_reference_result_table(summary)}
</section>
"""
    body = f"""
<div class="tar-header">
  <div>
    <h1>Módulo TAR</h1>
    <p class="muted-text">Avaliação radiológica ambiental em ambiente marinho a partir da planilha TAR.</p>
  </div>
  <nav class="scenario-tabs">{_scenario_tabs(summary['selected_scenario'])}</nav>
</div>
{_report_toc(_dashboard_toc_items(summary))}
<section class="panel report-block" id="introducao">
  <div class="cards">{card_html}</div>
  {_summary_intro(summary)}
  <div class="actions">
    <a class="button" href="/tar/report-preview?{_scenario_query_suffix(summary)}">Abrir relatório TAR</a>
    <a class="button" href="/tar/export-report.pdf?{_scenario_query_suffix(summary)}">Gerar PDF</a>
    <a class="button" href="/tar/artigo-beta?{_scenario_query_suffix(summary)}">ARTIGO BETA</a>
    <a class="button" href="/api/tar/summary?{_scenario_query_suffix(summary)}">Ver JSON</a>
  </div>
</section>
{_academic_methodology_panel(summary)}
{_total_activity_review_panel(summary)}
{legacy_reference_sections}
{_hypothetical_panel(summary)}
{_empirical_activity_panel(summary)}
{_statistical_comparison_panel(summary)}
<section class="panel report-block" id="suficiencia-estatistica">
  <h2>Discussão e conclusão</h2>
  <p>{escape(assessment['reason']) if not scenario.get('is_hypothetical') else 'No cenário hipotético, as medições sintéticas permitem aplicar teste inferencial sobre as razões simulado/Report Level. Para dados reais, a validade do teste depende de medições independentes da água do TAR.'}</p>
  {_minimums_table()}
</section>
"""
    return _base_html("Módulo TAR", body)


def render_tar_report_html(summary: dict[str, Any]) -> str:
    assessment = summary["inferential_assessment"]
    scenario = summary["scenario"]
    legacy_reference_sections = ""
    if not scenario.get("total_activity_review"):
        legacy_reference_sections = f"""
<section class="panel report-block" id="comparacao-normativa-cenario">
  <h2>Comparação com Report Level e LLD</h2>
  <p>A comparação com as referências disponíveis não indicou superação de Report Level. O LLD foi mantido como referência de detecção, sem ser tratado como teste inferencial ou limite de ação. Quando a bibliografia consultada não apresenta referência para o compartimento, o resultado foi classificado como sem referência.</p>
  {_reference_result_table(summary)}
</section>
"""
    body = f"""
<div class="tar-header">
  <div>
    <h1>Relatório TAR</h1>
    <p class="muted-text">Resumo técnico do cenário {escape(summary['scenario']['label'])}.</p>
  </div>
  <nav class="scenario-tabs">{_scenario_tabs(summary['selected_scenario'], base_path="/tar/artigo-beta")}</nav>
</div>
<section class="panel cover-panel" id="capa">
  <span class="cover-label">Relatório técnico</span>
  <h1 class="cover-title">{escape(REPORT_FULL_TITLE)}</h1>
  <p>Relatório do cenário {escape(summary['scenario']['label'])}, com auditoria da atividade total do TAR, cálculos por matriz ambiental, comparação com ERICA Tool e testes inferenciais.</p>
</section>
{_report_toc(_report_toc_items(summary))}
<section class="panel report-block" id="resumo">
  <h2>Resumo</h2>
  {_summary_intro(summary)}
  <p>O conjunto analisado reúne os radionuclídeos {escape(', '.join(summary['scenario']['radionuclides']))}. {'No cenário hipotético, o n se refere ao número de medições sintéticas por radionuclídeo.' if scenario.get('is_hypothetical') else 'O n informado nesta etapa corresponde à quantidade de radionuclídeos do modelo e não deve ser tratado como número de amostras ambientais independentes.'}</p>
</section>
{_academic_methodology_panel(summary)}
{_total_activity_review_panel(summary)}
{legacy_reference_sections}
{_hypothetical_panel(summary)}
{_empirical_activity_panel(summary)}
{_statistical_comparison_panel(summary)}
<section class="panel report-block" id="suficiencia-estatistica">
  <h2>Discussão e conclusão</h2>
  <p>{escape(assessment['status'])}: {escape(assessment['reason']) if not scenario.get('is_hypothetical') else 'O cenário hipotético usa medições sintéticas apenas para demonstrar o fluxo estatístico. Para conclusão real, as medições devem vir da espectrometria gama das amostras da água do TAR.'}</p>
  {_minimums_table()}
</section>
<section class="panel report-block" id="exportacao">
  <h2>Exportação</h2>
  <div class="actions">
    <a class="button" href="/tar/export-report.docx?{_scenario_query_suffix(summary)}">DOCX</a>
    <a class="button" href="/tar/export-report.pdf?{_scenario_query_suffix(summary)}">Gerar PDF</a>
    <a class="button" href="/tar/artigo-beta?{_scenario_query_suffix(summary)}">ARTIGO BETA</a>
  </div>
</section>
"""
    return _base_html("Relatório TAR", body)


def _load_article_blocks(article_path: str | Path) -> list[dict[str, str]]:
    path = Path(article_path)
    if not path.exists():
        raise RuntimeError(f"Arquivo do Artigo TAR não encontrado: {path}")
    if path.suffix.lower() == ".pdf":
        try:
            import fitz
        except Exception as exc:  # pragma: no cover - exercised only when dependency is missing
            raise RuntimeError("A biblioteca PyMuPDF não está disponível para ler o PDF do Artigo TAR.") from exc
        document = fitz.open(path)
        lines: list[str] = []
        for page in document:
            lines.extend(page.get_text("text").splitlines())
        document.close()
        return _article_pdf_blocks(lines)

    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - exercised only when dependency is missing
        raise RuntimeError("A biblioteca python-docx não está disponível para ler o Artigo TAR.") from exc

    document = Document(path)
    blocks: list[dict[str, str]] = []
    for paragraph in document.paragraphs:
        text = " ".join((paragraph.text or "").split())
        if not text:
            continue
        style = paragraph.style.name if paragraph.style else ""
        blocks.append({"text": text, "style": style})
    return blocks


def _article_heading_level(text: str) -> int | None:
    stripped = text.strip()
    if re.match(r"^\d+(\.\d+)*\.\s+\S", stripped):
        return 1 if re.match(r"^\d+\.\s+\S", stripped) else 2
    letters = [char for char in stripped if char.isalpha()]
    if letters and stripped.upper() == stripped and len(stripped) <= 120:
        return 1
    return None


def _article_pdf_blocks(lines: list[str]) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = " ".join(" ".join(line.split()) for line in paragraph_lines).strip()
        paragraph_lines.clear()
        if text:
            blocks.append({"text": text, "style": "PDF Paragraph"})

    for raw_line in lines:
        text = " ".join((raw_line or "").split())
        if not text:
            flush_paragraph()
            continue
        heading_level = _article_heading_level(text)
        if heading_level is not None:
            flush_paragraph()
            blocks.append({"text": text, "style": f"PDF Heading {heading_level}"})
            continue
        paragraph_lines.append(text)
        if text.endswith((".", ":", ";", "!", "?")):
            flush_paragraph()
    flush_paragraph()
    return blocks


def _article_block_html(block: dict[str, str]) -> str:
    text = block.get("text") or ""
    style = block.get("style") or ""
    if style.startswith("PDF Heading 1") or style.startswith("Heading 1"):
        return f"<h2>{escape(text)}</h2>"
    if style.startswith("PDF Heading") or style.startswith("Heading"):
        return f"<h3>{escape(text)}</h3>"
    if text.isupper() and len(text) <= 80:
        return f"<h2>{escape(text)}</h2>"
    return f"<p>{escape(text)}</p>"


def render_tar_article_beta_html(summary: dict[str, Any], article_path: str | Path) -> str:
    scenario = summary["scenario"]
    article_blocks = _load_article_blocks(article_path)
    article_html = "".join(_article_block_html(block) for block in article_blocks)
    article_filename = Path(article_path).name
    body = f"""
<div class="tar-header">
  <div>
    <h1>ARTIGO BETA</h1>
    <p class="muted-text">Versão de trabalho que separa dados calculados por fórmulas, dados simulados pelo ERICA Tool e normas de comparação.</p>
  </div>
  <nav class="scenario-tabs">{_scenario_tabs(summary['selected_scenario'], base_path="/tar/artigo-beta")}</nav>
</div>
<section class="panel cover-panel" id="capa">
  <span class="cover-label">Relatório técnico</span>
  <h1 class="cover-title">{escape(REPORT_FULL_TITLE)}</h1>
  <p>Este documento organiza os dados do módulo TAR em formato técnico, com separação entre dados calculados por fórmulas, valores simulados ou pareados pelo ERICA Tool, referências normativas e estatística inferencial.</p>
  <div class="cover-meta">
    <p><strong>Cenário:</strong> {escape(scenario['label'])}</p>
    <p><strong>Fonte editorial:</strong> {escape(article_filename)}. O texto-base foi lido diretamente do arquivo local e reorganizado para reduzir quebras artificiais de linha.</p>
    <p><strong>Correção conceitual:</strong> os valores da planilha são dados calculados por fórmulas; os dados simulados vêm do ERICA Tool; Report Level e LLD são normas fixas de comparação.</p>
  </div>
</section>
{_report_toc(_article_toc_items(summary))}
<section class="panel report-block" id="texto-artigo">
  <h2>Introdução e texto base</h2>
  <p class="article-source">Fonte: {escape(article_filename)}. O texto abaixo foi incorporado como base editorial e teve linhas quebradas reunidas em parágrafos coerentes.</p>
  <div class="article-text">{article_html}</div>
</section>
<section class="panel report-block" id="dados-relatorio">
  <h2>Dados do relatório TAR incorporados</h2>
  {_summary_intro(summary)}
  <p>Esta seção acrescenta ao artigo os resultados gerados no relatório TAR para o cenário {escape(scenario['label'])}. A terminologia distingue dados calculados por fórmulas, dados simulados pelo ERICA Tool e normas: Report Level e LLD.</p>
</section>
{_academic_methodology_panel(summary)}
{_total_activity_review_panel(summary)}
<section class="panel report-block" id="comparacao-normativa-cenario">
  <h2>Comparação com Report Level e LLD</h2>
  <p>A comparação aproxima o texto do artigo dos resultados quantitativos atuais. Report Level é tratado como critério de notificação; LLD permanece como referência de detecção.</p>
  {_reference_result_table(summary)}
</section>
{_hypothetical_panel(summary)}
{_empirical_activity_panel(summary)}
{_statistical_comparison_panel(summary)}
<section class="panel report-block" id="suficiencia-estatistica">
  <h2>Discussão e conclusão</h2>
  <p>{escape(summary['inferential_assessment']['status'])}: {escape(summary['inferential_assessment']['reason']) if not scenario.get('is_hypothetical') else 'O cenário hipotético usa medições sintéticas apenas para demonstrar o fluxo estatístico. Para conclusão real, as medições devem vir da espectrometria gama das amostras da água do TAR.'}</p>
  {_minimums_table()}
</section>
<section class="panel report-block" id="acoes">
  <h2>Ações</h2>
  <div class="actions">
    <a class="button" href="/tar?{_scenario_query_suffix(summary)}">Voltar ao TAR</a>
    <a class="button" href="/tar/report-preview?{_scenario_query_suffix(summary)}">Abrir relatório TAR</a>
    <a class="button" href="/tar/export-report.pdf?{_scenario_query_suffix(summary)}">Gerar PDF</a>
  </div>
</section>
"""
    return _base_html("ARTIGO BETA", body)
