from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .model import COMPARTMENTS, INFERENTIAL_TEST_MINIMUMS, SCENARIOS


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
    sensitivity_suffix = (
        f"&sensitivity_n={escape(str(sensitivity.get('sample_count') or 10000))}"
        f"&sensitivity_seed={escape(str(sensitivity.get('seed') or 20260504))}"
    )
    if not scenario.get("is_hypothetical"):
        return f"scenario={escape(str(summary['selected_scenario']))}{sensitivity_suffix}"
    return (
        f"scenario={escape(str(summary['selected_scenario']))}"
        f"&n={escape(str(scenario.get('measurement_count') or 60))}"
        f"&seed={escape(str(scenario.get('seed') or 20260504))}"
        f"{sensitivity_suffix}"
    )


def _explain_text(text: str) -> str:
    return f'<p class="explain-text">{escape(text)}</p>' if text else ""


def _tar_table(class_name: str, caption: str, header_html: str, body_html: str, note: str = "", intro: str = "") -> str:
    note_html = f'<p class="table-note">{escape(note)}</p>' if note else ""
    return (
        f"{_explain_text(intro)}"
        f'<table class="tar-table {class_name}">'
        f"<caption>{escape(caption)}</caption>"
        f"<thead>{header_html}</thead>"
        f"<tbody>{body_html}</tbody></table>"
        f"{note_html}"
    )


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
    )


def _hypothetical_panel(summary: dict[str, Any]) -> str:
    scenario = summary["scenario"]
    if not scenario.get("is_hypothetical"):
        return ""
    return f"""
<section class="panel">
  <h2>Medições sintéticas da água do TAR</h2>
  <p>O cenário hipotético parte dos valores medidos de entrada da planilha e gera {scenario['measurement_count']} medições sintéticas por radionuclídeo, com seed {scenario['seed']}. Esses valores representam uma série simulada de resultados de espectrometria gama da água do TAR e alimentam novas simulações dos compartimentos ambientais.</p>
  {_hypothetical_measurements_table(summary)}
</section>
<section class="panel">
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


def _base_html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light; --ink: #17313a; --muted: #607782; --line: #d8e2e6; --soft: #f3f7f8; --accent: #27667b; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--ink); background: #f6f8f9; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 42px; }}
    .tar-header {{ display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 22px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 26px 0 10px; font-size: 18px; letter-spacing: 0; }}
    h3 {{ margin: 18px 0 8px; font-size: 14px; letter-spacing: 0; }}
    p {{ line-height: 1.55; margin: 8px 0; }}
    .scenario-tabs {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .scenario-tab {{ display: inline-flex; border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px; color: var(--accent); text-decoration: none; background: #fff; }}
    .scenario-tab.selected {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .panel {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 18px; margin: 14px 0; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ background: var(--soft); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .card strong {{ display: block; font-size: 24px; margin-top: 6px; }}
    .muted-text {{ color: var(--muted); }}
    .tar-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; background: #fff; }}
    .tar-table caption {{ caption-side: top; text-align: left; font-weight: bold; color: #203f49; padding: 0 0 7px; }}
    .tar-table th, .tar-table td {{ border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }}
    .tar-table th {{ background: #eaf1f3; color: #203f49; font-size: 13px; }}
    .tar-table th span {{ display: block; color: var(--muted); font-weight: normal; font-size: 11px; }}
    .tar-table--dense th, .tar-table--dense td {{ font-size: 12px; }}
    .pill {{ display: inline-flex; border-radius: 999px; padding: 2px 8px; font-size: 12px; border: 1px solid var(--line); }}
    .pill.good {{ background: #edf8f0; color: #1f6b3a; border-color: #bfdfc8; }}
    .pill.bad {{ background: #fff0f0; color: #9a2424; border-color: #e6bbbb; }}
    .pill.muted {{ background: #f4f6f7; color: #607782; }}
    .explain-text {{ color: #405862; font-size: 13px; line-height: 1.5; margin: 10px 0 8px; }}
    .explain-box {{ border-left: 4px solid var(--accent); background: #f7fafb; padding: 10px 12px; margin: 12px 0; }}
    .explain-box p {{ color: #405862; font-size: 13px; line-height: 1.5; margin: 6px 0; }}
    .table-note {{ margin: 6px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .tar-chart {{ width: 100%; max-width: 520px; display: block; margin-top: 10px; }}
    .tar-chart--wide {{ max-width: 100%; }}
    .sensitivity-chart-grid {{ display: grid; gap: 14px; margin-top: 12px; }}
    .sensitivity-chart-grid article {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; overflow-x: auto; }}
    .sensitivity-cards {{ margin: 12px 0; }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }}
    .button {{ display: inline-flex; padding: 9px 12px; border-radius: 6px; background: var(--accent); color: #fff; text-decoration: none; }}
    .article-text h2 {{ margin-top: 20px; }}
    .article-text p {{ text-align: justify; }}
    .article-source {{ font-size: 12px; color: var(--muted); margin-bottom: 12px; }}
    @media (max-width: 760px) {{ .tar-header {{ display: block; }} .tar-table {{ display: block; overflow-x: auto; }} }}
  </style>
</head>
<body><main>{body}</main></body>
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


def render_tar_dashboard_html(summary: dict[str, Any]) -> str:
    scenario = summary["scenario"]
    assessment = summary["inferential_assessment"]
    inferential_label = "aplicável" if scenario.get("is_hypothetical") else "não aplicável"
    cards = [
        ("Radionuclídeos", str(scenario["radionuclide_count"])),
        ("Cenário", scenario["label"]),
        ("Report Level", "0 acima" if not scenario["has_reference_exceedance"] else f"{len(scenario['exceedances'])} acima"),
        ("Inferência", inferential_label),
    ]
    card_html = "".join(f'<div class="card"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>' for label, value in cards)
    body = f"""
<div class="tar-header">
  <div>
    <h1>Módulo TAR</h1>
    <p class="muted-text">Avaliação radiológica ambiental em ambiente marinho a partir da planilha TAR.</p>
  </div>
  <nav class="scenario-tabs">{_scenario_tabs(summary['selected_scenario'])}</nav>
</div>
<section class="panel">
  <div class="cards">{card_html}</div>
  {_summary_intro(summary)}
  <div class="actions">
    <a class="button" href="/tar/report-preview?{_scenario_query_suffix(summary)}">Abrir relatório TAR</a>
    <a class="button" href="/tar/artigo-beta?{_scenario_query_suffix(summary)}">ARTIGO BETA</a>
    <a class="button" href="/api/tar/summary?{_scenario_query_suffix(summary)}">Ver JSON</a>
  </div>
</section>
<section class="panel">
  <h2>Referências disponíveis</h2>
  <p>Água e peixe têm 4 referências disponíveis, sedimento tem 1 referência e invertebrado não tem referência cadastrada na planilha. O Report Level foi tratado como critério de notificação; o LLD permanece como referência de detecção.</p>
  {_reference_svg(summary)}
  {_reference_counts_table(summary)}
</section>
<section class="panel">
  <h2>Concentrações calculadas</h2>
  {_concentration_table(summary)}
</section>
<section class="panel">
  <h2>Comparação com Report Level e LLD</h2>
  {_reference_result_table(summary)}
</section>
{_hypothetical_panel(summary)}
{_sensitivity_panel(summary)}
<section class="panel">
  <h2>Suficiência estatística</h2>
  <p>{escape(assessment['reason']) if not scenario.get('is_hypothetical') else 'No cenário hipotético, as medições sintéticas permitem aplicar teste inferencial sobre as razões simulado/Report Level. Para dados reais, a validade do teste depende de medições independentes da água do TAR.'}</p>
  {_minimums_table()}
</section>
"""
    return _base_html("Módulo TAR", body)


def render_tar_report_html(summary: dict[str, Any]) -> str:
    assessment = summary["inferential_assessment"]
    scenario = summary["scenario"]
    body = f"""
<div class="tar-header">
  <div>
    <h1>Relatório TAR</h1>
    <p class="muted-text">Resumo técnico do cenário {escape(summary['scenario']['label'])}.</p>
  </div>
  <nav class="scenario-tabs">{_scenario_tabs(summary['selected_scenario'], base_path="/tar/artigo-beta")}</nav>
</div>
<section class="panel">
  <h2>Resumo</h2>
  {_summary_intro(summary)}
  <p>O conjunto analisado reúne os radionuclídeos {escape(', '.join(summary['scenario']['radionuclides']))}. {'No cenário hipotético, o n se refere ao número de medições sintéticas por radionuclídeo.' if scenario.get('is_hypothetical') else 'O n informado nesta etapa corresponde à quantidade de radionuclídeos do modelo e não deve ser tratado como número de amostras ambientais independentes.'}</p>
</section>
<section class="panel">
  <h2>Comparação com Report Level e LLD</h2>
  <p>A comparação com as referências disponíveis não indicou superação de Report Level. O LLD foi mantido como referência de detecção, sem ser tratado como teste inferencial ou limite de ação. Quando a bibliografia consultada não apresenta referência para o compartimento, o resultado foi classificado como sem referência.</p>
  {_reference_result_table(summary)}
</section>
{_hypothetical_panel(summary)}
{_sensitivity_panel(summary)}
<section class="panel">
  <h2>Suficiência estatística</h2>
  <p>{escape(assessment['status'])}: {escape(assessment['reason']) if not scenario.get('is_hypothetical') else 'O cenário hipotético usa medições sintéticas apenas para demonstrar o fluxo estatístico. Para conclusão real, as medições devem vir da espectrometria gama das amostras da água do TAR.'}</p>
  {_minimums_table()}
</section>
<section class="panel">
  <h2>Exportação</h2>
  <div class="actions">
    <a class="button" href="/tar/export-report.docx?{_scenario_query_suffix(summary)}">DOCX</a>
    <a class="button" href="/tar/export-report.pdf?{_scenario_query_suffix(summary)}">PDF</a>
    <a class="button" href="/tar/artigo-beta?{_scenario_query_suffix(summary)}">ARTIGO BETA</a>
  </div>
</section>
"""
    return _base_html("Relatório TAR", body)


def _load_article_docx_blocks(article_path: str | Path) -> list[dict[str, str]]:
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - exercised only when dependency is missing
        raise RuntimeError("A biblioteca python-docx não está disponível para ler o Artigo TAR.") from exc

    path = Path(article_path)
    if not path.exists():
        raise RuntimeError(f"Arquivo Artigo TAR.docx não encontrado: {path}")

    document = Document(path)
    blocks: list[dict[str, str]] = []
    for paragraph in document.paragraphs:
        text = " ".join((paragraph.text or "").split())
        if not text:
            continue
        style = paragraph.style.name if paragraph.style else ""
        blocks.append({"text": text, "style": style})
    return blocks


def _article_block_html(block: dict[str, str]) -> str:
    text = block.get("text") or ""
    style = block.get("style") or ""
    if style.startswith("Heading 1"):
        return f"<h2>{escape(text)}</h2>"
    if style.startswith("Heading"):
        return f"<h3>{escape(text)}</h3>"
    if text.isupper() and len(text) <= 80:
        return f"<h2>{escape(text)}</h2>"
    return f"<p>{escape(text)}</p>"


def render_tar_article_beta_html(summary: dict[str, Any], article_path: str | Path) -> str:
    scenario = summary["scenario"]
    article_blocks = _load_article_docx_blocks(article_path)
    article_html = "".join(_article_block_html(block) for block in article_blocks)
    body = f"""
<div class="tar-header">
  <div>
    <h1>ARTIGO BETA</h1>
    <p class="muted-text">Versão de trabalho que reúne o texto-base do Artigo TAR com os resultados calculados no módulo TAR.</p>
  </div>
  <nav class="scenario-tabs">{_scenario_tabs(summary['selected_scenario'], report=True)}</nav>
</div>
<section class="panel">
  <h2>Texto incorporado do Artigo TAR</h2>
  <p class="article-source">Fonte: {escape(str(Path(article_path).name))}. O texto abaixo foi lido diretamente do arquivo DOCX local e mantido como base editorial.</p>
  <div class="article-text">{article_html}</div>
</section>
<section class="panel">
  <h2>Dados do relatório TAR incorporados</h2>
  {_summary_intro(summary)}
  <p>Esta seção acrescenta ao artigo os resultados gerados no relatório TAR para o cenário {escape(scenario['label'])}. A terminologia preserva Report Level, LLD, P95 e probabilidade empírica conforme usados no módulo.</p>
</section>
<section class="panel">
  <h2>Comparação com Report Level e LLD</h2>
  <p>A tabela abaixo aproxima o texto do artigo dos resultados quantitativos atuais. Report Level é tratado como critério de notificação; LLD permanece como referência de detecção.</p>
  {_reference_result_table(summary)}
</section>
{_hypothetical_panel(summary)}
{_sensitivity_panel(summary)}
<section class="panel">
  <h2>Suficiência estatística</h2>
  <p>{escape(summary['inferential_assessment']['status'])}: {escape(summary['inferential_assessment']['reason']) if not scenario.get('is_hypothetical') else 'O cenário hipotético usa medições sintéticas apenas para demonstrar o fluxo estatístico. Para conclusão real, as medições devem vir da espectrometria gama das amostras da água do TAR.'}</p>
  {_minimums_table()}
</section>
<section class="panel">
  <h2>Ações</h2>
  <div class="actions">
    <a class="button" href="/tar?{_scenario_query_suffix(summary)}">Voltar ao TAR</a>
    <a class="button" href="/tar/report-preview?{_scenario_query_suffix(summary)}">Abrir relatório TAR</a>
  </div>
</section>
"""
    return _base_html("ARTIGO BETA", body)
