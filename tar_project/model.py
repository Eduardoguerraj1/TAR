from __future__ import annotations

import math
import random
import re
import statistics
from pathlib import Path
from typing import Any

import openpyxl
from scipy import stats


class TarWorkbookError(RuntimeError):
    """Raised when the TAR workbook cannot be loaded into the expected model."""


SCENARIOS: dict[str, dict[str, str]] = {
    "a1": {"key": "a1", "sheet": "A1", "label": "Angra 1"},
    "a1_a2": {"key": "a1_a2", "sheet": "A1 e A2", "label": "Angra 1 e Angra 2"},
    "hipotetico": {"key": "hipotetico", "sheet": "", "label": "Cenário hipotético"},
}

EXPECTED_RADIONUCLIDES = ["Co-58", "Co-60", "Cr-51", "Cs-137", "Mn-54", "Sb-124", "Sb-125", "Zr-95"]
EMPIRICAL_ACTIVITY_RADIONUCLIDES = ["Co-58", "Co-60", "Cr-51", "Cs-137", "Mn-54", "Nb-95", "Sb-124", "Sb-125", "Zr-95"]
EMPIRICAL_ACTIVITY_GROUPS = ["TAR - Afluente", "TAR - Efluente"]
EMPIRICAL_ACTIVITY_DEFAULT_FILENAME = "Atividade Total TAR c radionuclideos.xls"

COMPARTMENTS: list[dict[str, Any]] = [
    {
        "key": "water",
        "label": "Água",
        "unit": "Bq/m³",
        "value_col": 7,
        "report_level_col": 19,
        "lld_col": 18,
    },
    {
        "key": "fish",
        "label": "Peixe",
        "unit": "Bq/kg",
        "value_col": 12,
        "report_level_col": 21,
        "lld_col": 20,
    },
    {
        "key": "invertebrate",
        "label": "Invertebrado",
        "unit": "Bq/kg",
        "value_col": 13,
        "report_level_col": 23,
        "lld_col": 22,
    },
    {
        "key": "sediment",
        "label": "Sedimento",
        "unit": "Bq/kg",
        "value_col": 16,
        "report_level_col": 25,
        "lld_col": 24,
    },
]

INFERENTIAL_TEST_MINIMUMS: list[dict[str, str]] = [
    {"test": "Shapiro-Wilk", "technical_minimum": "n >= 3", "recommended": "n >= 8 a 10 por grupo"},
    {"test": "Levene", "technical_minimum": "2 grupos, n >= 2 por grupo", "recommended": "n >= 5 por grupo"},
    {"test": "Teste t pareado", "technical_minimum": "n >= 2 pares", "recommended": "n >= 10 pares; n >= 3 para checar normalidade"},
    {"test": "Wilcoxon pareado", "technical_minimum": "pares não nulos", "recommended": "n >= 10 pares"},
    {"test": "Teste t independente", "technical_minimum": "2 grupos, n >= 2 por grupo", "recommended": "n >= 10 por grupo"},
    {"test": "Mann-Whitney U", "technical_minimum": "2 grupos, n >= 1 por grupo", "recommended": "n >= 5 a 10 por grupo"},
    {"test": "ANOVA uma via", "technical_minimum": "2+ grupos, n >= 2 por grupo", "recommended": "n >= 5 por grupo"},
    {"test": "Kruskal-Wallis", "technical_minimum": "2+ grupos", "recommended": "n >= 5 por grupo"},
    {"test": "ANOVA medidas repetidas", "technical_minimum": "3+ condições e 3+ unidades completas", "recommended": "n >= 10 unidades completas"},
    {"test": "Friedman", "technical_minimum": "3+ condições pareadas", "recommended": "n >= 10 unidades completas"},
    {"test": "Pearson/Spearman", "technical_minimum": "n >= 3 pares", "recommended": "n >= 10 a 20 pares"},
]

DEFAULT_SENSITIVITY_N = 10000
DEFAULT_SENSITIVITY_SEED = 20260504
DEFAULT_TAR_ACTIVITY_BQ_YEAR = 2.69e11
DEFAULT_DILUTION_FLOW_M3_YEAR = 2.96e9
DEFAULT_STAT_N = 60
DEFAULT_STAT_SEED = 20260504

ERICA_TOOL_VALUES: dict[str, dict[str, float | None]] = {
    # Fonte: tabela/screenshot do ERICA Tool no arquivo "Artigo TAR1 correção.pdf".
    # Água foi extraída em Bq/L no ERICA Tool e convertida para Bq/m³ para comparação com a planilha.
    "Co-58": {"water": 1.85e-2 * 1000.0, "fish": 6.30e1, "invertebrate": 4.47e1, "sediment": 3.27e0},
    "Co-60": {"water": 8.30e-4 * 1000.0, "fish": 2.94e0, "invertebrate": 2.81e0, "sediment": 3.91e0},
    "Cr-51": {"water": 4.08e-3 * 1000.0, "fish": 2.35e-1, "invertebrate": 4.27e-1, "sediment": 2.80e-1},
    "Cs-137": {"water": 8.69e-5 * 1000.0, "fish": 7.09e-3, "invertebrate": 5.32e-3, "sediment": 1.19e0},
    "Mn-54": {"water": 1.95e-4 * 1000.0, "fish": 1.59e0, "invertebrate": 1.04e0, "sediment": 1.52e-1},
    "Sb-124": {"water": 5.18e-4 * 1000.0, "fish": 1.00e-3, "invertebrate": 6.40e-2, "sediment": 7.78e-2},
    "Sb-125": {"water": 1.41e-4 * 1000.0, "fish": 3.97e-4, "invertebrate": 2.55e-2, "sediment": 3.55e-1},
    "Zr-95": {"water": 6.66e-5 * 1000.0, "fish": 3.88e-3, "invertebrate": 2.15e-3, "sediment": 5.31e-3},
}


def resolve_tar_scenario_key(value: Any) -> str:
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "a1",
        "angra_1": "a1",
        "angra1": "a1",
        "a1": "a1",
        "a1ea2": "a1_a2",
        "a1_e_a2": "a1_a2",
        "a1_a2": "a1_a2",
        "angra_1_e_2": "a1_a2",
        "angra_1_e_angra_2": "a1_a2",
        "hipotetico": "hipotetico",
        "hipotético": "hipotetico",
        "cenario_hipotetico": "hipotetico",
        "cenário_hipotético": "hipotetico",
    }
    return aliases.get(key, key if key in SCENARIOS else "a1")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _to_float(value: Any) -> float | None:
    if _is_number(value):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text or text == "*":
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _format_scientific(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2E}".replace("E+0", "E+").replace("E-0", "E-")


def _format_p_value(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "—"
    if value < 0.0001:
        return "p < 0,0001"
    return f"p = {value:.4f}".replace(".", ",")


def _format_decimal(value: float | None, *, digits: int = 4) -> str:
    if value is None or not math.isfinite(value):
        return "—"
    return f"{value:.{digits}f}".replace(".", ",")


def _format_percent(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "—"
    return f"{value * 100:.2f}%".replace(".", ",")


def _summary_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "mean": None,
            "stdev": None,
            "cv": None,
            "q1": None,
            "median": None,
            "q3": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    ordered = sorted(values)
    quartiles = statistics.quantiles(ordered, n=4, method="inclusive") if len(ordered) > 1 else [ordered[0], ordered[0], ordered[0]]
    mean = statistics.fmean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "n": len(values),
        "mean": mean,
        "stdev": stdev,
        "cv": stdev / mean if mean else None,
        "q1": quartiles[0],
        "median": statistics.median(values),
        "q3": quartiles[2],
        "p95": statistics.quantiles(ordered, n=100, method="inclusive")[94] if len(ordered) > 1 else ordered[0],
        "min": ordered[0],
        "max": ordered[-1],
    }


def _ratio_status(value: float | None, reference: float | None) -> dict[str, Any]:
    if value is None or reference is None or reference <= 0:
        return {"reference": reference, "ratio": None, "status": "sem referência"}
    ratio = value / reference
    return {"reference": reference, "ratio": ratio, "status": "abaixo" if ratio <= 1.0 else "acima"}


def _read_radionuclide_rows(ws: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index in range(1, ws.max_row + 1):
        radionuclide = ws.cell(row_index, 2).value
        if not isinstance(radionuclide, str) or not re.match(r"^[A-Z][a-z]?-\d+", radionuclide.strip()):
            continue
        item: dict[str, Any] = {
            "row": row_index,
            "radionuclide": radionuclide.strip(),
            "source_concentration_bq_m3": _to_float(ws.cell(row_index, 3).value),
            "fraction": _to_float(ws.cell(row_index, 4).value),
            "activity_bq": _to_float(ws.cell(row_index, 5).value),
            "compartments": {},
        }
        for compartment in COMPARTMENTS:
            value = _to_float(ws.cell(row_index, compartment["value_col"]).value)
            report_level = _to_float(ws.cell(row_index, compartment["report_level_col"]).value)
            lld = _to_float(ws.cell(row_index, compartment["lld_col"]).value)
            report_result = _ratio_status(value, report_level)
            lld_result = _ratio_status(value, lld)
            item["compartments"][compartment["key"]] = {
                "label": compartment["label"],
                "unit": compartment["unit"],
                "value": value,
                "value_text": _format_scientific(value),
                "report_level": report_result["reference"],
                "report_level_text": _format_scientific(report_result["reference"]),
                "report_level_ratio": report_result["ratio"],
                "report_level_ratio_text": f"{report_result['ratio']:.4f}".replace(".", ",") if report_result["ratio"] is not None else "—",
                "report_level_status": report_result["status"],
                "lld": lld_result["reference"],
                "lld_text": _format_scientific(lld_result["reference"]),
                "lld_ratio": lld_result["ratio"],
                "lld_ratio_text": f"{lld_result['ratio']:.4f}".replace(".", ",") if lld_result["ratio"] is not None else "—",
                "lld_status": lld_result["status"],
            }
        rows.append(item)
    return rows


def _scenario_totals(ws: Any) -> dict[str, Any]:
    return {
        "total_water_concentration_bq_m3": _to_float(ws.cell(13, 7).value),
        "circulation_flow_m3_year": _to_float(ws.cell(17, 5).value),
        "tar_capacity_m3": _to_float(ws.cell(17, 3).value),
        "activity_bq_year": _to_float(ws.cell(18, 3).value),
    }


def _build_reference_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for compartment in COMPARTMENTS:
        key = compartment["key"]
        report_refs = [
            row["radionuclide"]
            for row in rows
            if row["compartments"][key]["report_level"] is not None
        ]
        lld_refs = [
            row["radionuclide"]
            for row in rows
            if row["compartments"][key]["lld"] is not None
        ]
        counts[key] = {
            "label": compartment["label"],
            "report_level": len(report_refs),
            "lld": len(lld_refs),
            "report_level_radionuclides": report_refs,
            "lld_radionuclides": lld_refs,
        }
    return counts


def _build_exceedances(rows: list[dict[str, Any]], *, reference: str) -> list[dict[str, Any]]:
    exceedances: list[dict[str, Any]] = []
    status_key = "report_level_status" if reference == "Report Level" else "lld_status"
    ratio_key = "report_level_ratio" if reference == "Report Level" else "lld_ratio"
    for row in rows:
        for compartment in COMPARTMENTS:
            result = row["compartments"][compartment["key"]]
            if result[status_key] != "acima":
                continue
            exceedances.append(
                {
                    "radionuclide": row["radionuclide"],
                    "compartment": compartment["label"],
                    "reference": reference,
                    "value": result["value"],
                    "ratio": result[ratio_key],
                }
            )
    return exceedances


def _scenario_summary(scenario_key: str, ws: Any) -> dict[str, Any]:
    rows = _read_radionuclide_rows(ws)
    if not rows:
        raise TarWorkbookError(f"Nenhum radionuclídeo foi encontrado na aba {ws.title!r}.")
    reference_counts = _build_reference_counts(rows)
    report_level_exceedances = _build_exceedances(rows, reference="Report Level")
    lld_exceedances = _build_exceedances(rows, reference="LLD")
    return {
        "key": scenario_key,
        "sheet": ws.title,
        "label": SCENARIOS[scenario_key]["label"],
        "radionuclide_count": len(rows),
        "radionuclides": [row["radionuclide"] for row in rows],
        "expected_radionuclides": EXPECTED_RADIONUCLIDES,
        "rows": rows,
        "totals": _scenario_totals(ws),
        "reference_counts": reference_counts,
        "exceedances": report_level_exceedances,
        "report_level_exceedances": report_level_exceedances,
        "lld_exceedances": lld_exceedances,
        "has_reference_exceedance": bool(report_level_exceedances),
        "has_lld_exceedance": bool(lld_exceedances),
    }


def _safe_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _generate_positive_measurements(base_value: float, count: int, rng: random.Random) -> list[float]:
    sigma = 0.18
    measurements: list[float] = []
    for _ in range(count):
        measurement = rng.lognormvariate(math.log(max(base_value, 1e-12)), sigma)
        measurements.append(measurement)
    return measurements


def _sensitivity_variable_specs(base_activity: float, base_flow: float) -> list[dict[str, Any]]:
    return [
        {
            "key": "activity_factor",
            "label": "Atividade total do TAR",
            "distribution": "Triangular",
            "parameters": "0,50x / 0,75x / 1,00x",
            "base_value": base_activity,
            "base_value_text": _format_scientific(base_activity),
            "unit": "Bq/ano",
            "description": "Multiplicador sintético aplicado à atividade total descarregada pelo TAR.",
        },
        {
            "key": "flow_factor",
            "label": "Vazão de diluição",
            "distribution": "Triangular",
            "parameters": "0,75x / 1,00x / 1,25x",
            "base_value": base_flow,
            "base_value_text": _format_scientific(base_flow),
            "unit": "m³/ano",
            "description": "Multiplicador sintético da vazão; valores maiores reduzem a concentração por diluição.",
        },
        {
            "key": "fish_bio_factor",
            "label": "Fator de bioacumulação - peixe",
            "distribution": "Lognormal",
            "parameters": "mediana 1,00x; sigma 0,35",
            "base_value": 1.0,
            "base_value_text": "1,00x",
            "unit": "multiplicador",
            "description": "Variação sintética do fator de bioacumulação para peixes.",
        },
        {
            "key": "invertebrate_bio_factor",
            "label": "Fator de bioacumulação - invertebrado",
            "distribution": "Lognormal",
            "parameters": "mediana 1,00x; sigma 0,50",
            "base_value": 1.0,
            "base_value_text": "1,00x",
            "unit": "multiplicador",
            "description": "Variação sintética do fator de bioacumulação para invertebrados.",
        },
        {
            "key": "sediment_transfer_factor",
            "label": "Transferência para sedimento",
            "distribution": "Lognormal",
            "parameters": "mediana 1,00x; sigma 0,65",
            "base_value": 1.0,
            "base_value_text": "1,00x",
            "unit": "multiplicador",
            "description": "Variação sintética agregando Kd/Kc e transferência sedimentar.",
        },
        {
            "key": "exposure_factor",
            "label": "Tempo de exposição",
            "distribution": "Uniforme",
            "parameters": "0,50x a 1,50x",
            "base_value": 1.0,
            "base_value_text": "1,00x",
            "unit": "multiplicador",
            "description": "Multiplicador sintético do tempo de exposição nos compartimentos biota e sedimento.",
        },
    ]


def _sample_sensitivity_variables(rng: random.Random) -> dict[str, float]:
    return {
        "activity_factor": rng.triangular(0.50, 1.00, 0.75),
        "flow_factor": rng.triangular(0.75, 1.25, 1.00),
        "fish_bio_factor": rng.lognormvariate(0.0, 0.35),
        "invertebrate_bio_factor": rng.lognormvariate(0.0, 0.50),
        "sediment_transfer_factor": rng.lognormvariate(0.0, 0.65),
        "exposure_factor": rng.uniform(0.50, 1.50),
    }


def _sensitivity_multiplier(compartment_key: str, variables: dict[str, float]) -> float:
    water_multiplier = variables["activity_factor"] / variables["flow_factor"]
    if compartment_key == "fish":
        return water_multiplier * variables["fish_bio_factor"] * variables["exposure_factor"]
    if compartment_key == "invertebrate":
        return water_multiplier * variables["invertebrate_bio_factor"] * variables["exposure_factor"]
    if compartment_key == "sediment":
        return water_multiplier * variables["sediment_transfer_factor"] * variables["exposure_factor"]
    return water_multiplier


def _build_histogram(values: list[float], *, bin_count: int = 12) -> list[dict[str, Any]]:
    if not values:
        return []
    lower = min(values)
    upper = max(values)
    if not math.isfinite(lower) or not math.isfinite(upper):
        return []
    if upper <= lower:
        upper = lower + 1.0
    step = (upper - lower) / bin_count
    counts = [0 for _ in range(bin_count)]
    for value in values:
        index = min(bin_count - 1, max(0, int((value - lower) / step)))
        counts[index] += 1
    return [
        {
            "start": lower + index * step,
            "end": lower + (index + 1) * step,
            "count": count,
            "label": f"{_format_decimal(lower + index * step, digits=2)}-{_format_decimal(lower + (index + 1) * step, digits=2)}",
        }
        for index, count in enumerate(counts)
    ]


def _build_sensitivity_analysis(scenario: dict[str, Any], *, sample_count: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    totals = scenario.get("totals") or {}
    base_activity = totals.get("activity_bq_year") or DEFAULT_TAR_ACTIVITY_BQ_YEAR
    base_flow = totals.get("circulation_flow_m3_year") or DEFAULT_DILUTION_FLOW_M3_YEAR
    variable_specs = _sensitivity_variable_specs(float(base_activity), float(base_flow))
    variable_samples: dict[str, list[float]] = {spec["key"]: [] for spec in variable_specs}
    value_samples: dict[tuple[str, str], list[float]] = {}
    exceedance_counts: dict[tuple[str, str], int] = {}
    max_report_level_ratios: list[float] = []

    rows = scenario.get("rows") or []
    for row in rows:
        for compartment in COMPARTMENTS:
            value_samples[(row["radionuclide"], compartment["key"])] = []
            exceedance_counts[(row["radionuclide"], compartment["key"])] = 0

    for _ in range(sample_count):
        variables = _sample_sensitivity_variables(rng)
        for key, value in variables.items():
            variable_samples[key].append(value)
        sample_ratios: list[float] = []
        for row in rows:
            for compartment in COMPARTMENTS:
                compartment_key = compartment["key"]
                data = row["compartments"][compartment_key]
                base_value = data.get("value")
                if base_value is None:
                    continue
                value = float(base_value) * _sensitivity_multiplier(compartment_key, variables)
                sample_key = (row["radionuclide"], compartment_key)
                value_samples[sample_key].append(value)
                report_level = data.get("report_level")
                if report_level is not None and report_level > 0:
                    ratio = value / float(report_level)
                    sample_ratios.append(ratio)
                    if ratio > 1.0:
                        exceedance_counts[sample_key] += 1
        max_report_level_ratios.append(max(sample_ratios) if sample_ratios else 0.0)

    summary_rows: list[dict[str, Any]] = []
    for row in rows:
        for compartment in COMPARTMENTS:
            compartment_key = compartment["key"]
            data = row["compartments"][compartment_key]
            sample_key = (row["radionuclide"], compartment_key)
            stats_summary = _summary_stats(value_samples.get(sample_key, []))
            report_level = data.get("report_level")
            p95 = stats_summary["p95"]
            p95_ratio = (p95 / report_level) if p95 is not None and report_level is not None and report_level > 0 else None
            exceedance_probability = (
                exceedance_counts.get(sample_key, 0) / sample_count
                if report_level is not None and report_level > 0
                else None
            )
            summary_rows.append(
                {
                    "radionuclide": row["radionuclide"],
                    "compartment": compartment["label"],
                    "compartment_key": compartment_key,
                    "unit": compartment["unit"],
                    "mean": stats_summary["mean"],
                    "mean_text": _format_scientific(stats_summary["mean"]),
                    "min": stats_summary["min"],
                    "min_text": _format_scientific(stats_summary["min"]),
                    "max": stats_summary["max"],
                    "max_text": _format_scientific(stats_summary["max"]),
                    "p95": p95,
                    "p95_text": _format_scientific(p95),
                    "report_level": report_level,
                    "report_level_text": _format_scientific(report_level),
                    "p95_report_level_ratio": p95_ratio,
                    "p95_report_level_ratio_text": _format_decimal(p95_ratio),
                    "exceedance_probability": exceedance_probability,
                    "exceedance_probability_text": _format_percent(exceedance_probability),
                }
            )

    influence_rows: list[dict[str, Any]] = []
    for spec in variable_specs:
        correlation = 0.0
        try:
            result = stats.spearmanr(variable_samples[spec["key"]], max_report_level_ratios)
            raw_correlation = float(result.correlation)
            correlation = raw_correlation if math.isfinite(raw_correlation) else 0.0
        except Exception:
            correlation = 0.0
        influence_rows.append(
            {
                "key": spec["key"],
                "label": spec["label"],
                "correlation": correlation,
                "correlation_text": _format_decimal(correlation, digits=3),
                "absolute_correlation": abs(correlation),
                "absolute_correlation_text": _format_decimal(abs(correlation), digits=3),
                "direction": "aumenta" if correlation > 0 else "reduz" if correlation < 0 else "neutra",
            }
        )
    influence_rows.sort(key=lambda item: item["absolute_correlation"], reverse=True)

    referenced_rows = [row for row in summary_rows if row["exceedance_probability"] is not None]
    max_exceedance_row = max(referenced_rows, key=lambda item: item["exceedance_probability"], default=None)
    max_ratio_row = max(referenced_rows, key=lambda item: item["p95_report_level_ratio"] or -1.0, default=None)
    dominant = influence_rows[0] if influence_rows else None
    max_ratio_stats = _summary_stats(max_report_level_ratios)
    narrative_text = (
        f"A análise de sensibilidade Monte Carlo executou {sample_count} cenários sintéticos com seed {seed}. "
        "O seed é o número que inicializa o sorteio pseudoaleatório; mantendo o mesmo seed, o sistema reproduz exatamente os mesmos cenários. "
        "Os intervalos são demonstrativos e aplicam multiplicadores simples sobre os resultados atuais do TAR, "
        "servindo para triagem exploratória das variáveis que mais aproximam os resultados do Report Level."
    )

    return {
        "sample_count": sample_count,
        "seed": seed,
        "synthetic": True,
        "source_note": "Intervalos sintéticos demonstrativos; não substituem constantes de literatura nem conclusão regulatória.",
        "base_activity_bq_year": float(base_activity),
        "base_activity_bq_year_text": _format_scientific(float(base_activity)),
        "base_flow_m3_year": float(base_flow),
        "base_flow_m3_year_text": _format_scientific(float(base_flow)),
        "variables": variable_specs,
        "summary_rows": summary_rows,
        "influence_rows": influence_rows,
        "narrative_text": narrative_text,
        "cards": [
            {"label": "Simulações", "value": f"{sample_count:,}".replace(",", ".")},
            {"label": "Seed reprodutível", "value": str(seed)},
            {
                "label": "Maior prob. > Report Level",
                "value": max_exceedance_row["exceedance_probability_text"] if max_exceedance_row else "—",
            },
            {"label": "Variável dominante", "value": dominant["label"] if dominant else "—"},
        ],
        "max_exceedance_row": max_exceedance_row,
        "max_ratio_row": max_ratio_row,
        "max_report_level_ratio_stats": {
            **max_ratio_stats,
            "min_text": _format_decimal(max_ratio_stats["min"], digits=3),
            "q1_text": _format_decimal(max_ratio_stats["q1"], digits=3),
            "median_text": _format_decimal(max_ratio_stats["median"], digits=3),
            "q3_text": _format_decimal(max_ratio_stats["q3"], digits=3),
            "mean_text": _format_decimal(max_ratio_stats["mean"], digits=3),
            "p95_text": _format_decimal(max_ratio_stats["p95"], digits=3),
            "max_text": _format_decimal(max_ratio_stats["max"], digits=3),
        },
        "chart_payloads": {
            "tornado": {"rows": influence_rows},
            "heatmap": {
                "compartments": [{"key": item["key"], "label": item["label"]} for item in COMPARTMENTS],
                "radionuclides": [row["radionuclide"] for row in rows],
                "cells": [
                    {
                        "radionuclide": row["radionuclide"],
                        "compartment": row["compartment"],
                        "compartment_key": row["compartment_key"],
                        "probability": row["exceedance_probability"],
                        "probability_text": row["exceedance_probability_text"],
                    }
                    for row in summary_rows
                ],
            },
            "histogram": {
                "bins": _build_histogram(max_report_level_ratios),
                "reference": 1.0,
                "reference_label": "Report Level",
            },
            "boxplot": {
                "stats": {
                    "min": max_ratio_stats["min"],
                    "q1": max_ratio_stats["q1"],
                    "median": max_ratio_stats["median"],
                    "q3": max_ratio_stats["q3"],
                    "max": max_ratio_stats["max"],
                    "p95": max_ratio_stats["p95"],
                    "min_text": _format_decimal(max_ratio_stats["min"], digits=3),
                    "q1_text": _format_decimal(max_ratio_stats["q1"], digits=3),
                    "median_text": _format_decimal(max_ratio_stats["median"], digits=3),
                    "q3_text": _format_decimal(max_ratio_stats["q3"], digits=3),
                    "max_text": _format_decimal(max_ratio_stats["max"], digits=3),
                    "p95_text": _format_decimal(max_ratio_stats["p95"], digits=3),
                },
                "reference": 1.0,
                "reference_label": "Report Level",
            },
        },
    }


def _stat_text(value: float | None, *, digits: int = 4) -> str:
    return _format_decimal(value, digits=digits)


def _stats_summary_with_text(values: list[float]) -> dict[str, Any]:
    summary = _summary_stats(values)
    return {
        **summary,
        "mean_text": _format_scientific(summary["mean"]),
        "stdev_text": _format_scientific(summary["stdev"]),
        "cv_text": _format_percent(summary["cv"]),
        "q1_text": _format_scientific(summary["q1"]),
        "median_text": _format_scientific(summary["median"]),
        "q3_text": _format_scientific(summary["q3"]),
        "p95_text": _format_scientific(summary["p95"]),
        "min_text": _format_scientific(summary["min"]),
        "max_text": _format_scientific(summary["max"]),
    }


def _is_mda_marker(value: Any) -> bool:
    return isinstance(value, str) and "MDA" in value.upper()


def _raw_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if _is_number(value):
        return _format_scientific(float(value))
    return str(value)


def _format_count(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _empirical_activity_path(workbook_path: str | Path, activity_workbook_path: str | Path | None) -> Path:
    if activity_workbook_path is not None:
        return Path(activity_workbook_path)
    return Path(workbook_path).resolve().parent / EMPIRICAL_ACTIVITY_DEFAULT_FILENAME


def _load_empirical_activity_records(path: str | Path) -> dict[str, Any]:
    activity_path = Path(path)
    if not activity_path.exists():
        raise TarWorkbookError(f"Planilha de atividade total TAR não encontrada: {activity_path}")
    try:
        import xlrd
    except Exception as exc:  # pragma: no cover - exercised only when dependency is missing
        raise TarWorkbookError("A biblioteca xlrd não está disponível para ler a planilha .xls de atividade total TAR.") from exc

    try:
        workbook = xlrd.open_workbook(str(activity_path))
    except Exception as exc:
        raise TarWorkbookError(f"Não foi possível abrir a planilha de atividade total TAR: {exc}") from exc
    if not workbook.sheet_names():
        raise TarWorkbookError("A planilha de atividade total TAR não contém abas.")

    sheet = workbook.sheet_by_index(0)
    headers = [" ".join(str(sheet.cell_value(0, col)).split()) for col in range(sheet.ncols)]
    radionuclide_columns: dict[str, int] = {}
    for col, header in enumerate(headers):
        match = re.match(r"^([A-Z][a-z]?-\d+)\b", header)
        if match and match.group(1) in EMPIRICAL_ACTIVITY_RADIONUCLIDES:
            radionuclide_columns[match.group(1)] = col
    missing = [radionuclide for radionuclide in EMPIRICAL_ACTIVITY_RADIONUCLIDES if radionuclide not in radionuclide_columns]
    if missing:
        raise TarWorkbookError(f"Radionuclídeos ausentes na planilha de atividade total TAR: {', '.join(missing)}")

    records: list[dict[str, Any]] = []
    for row_index in range(1, sheet.nrows):
        sample_id = str(sheet.cell_value(row_index, 0)).strip()
        group = " ".join(str(sheet.cell_value(row_index, 1)).split())
        if not sample_id and not group:
            continue
        if group not in EMPIRICAL_ACTIVITY_GROUPS:
            continue

        date_value = sheet.cell_value(row_index, 2)
        date_text = ""
        if _is_number(date_value):
            try:
                date_text = xlrd.xldate_as_datetime(float(date_value), workbook.datemode).date().isoformat()
            except Exception:
                date_text = _raw_text(date_value)
        else:
            date_text = _raw_text(date_value)

        activity_raw = sheet.cell_value(row_index, 3)
        activity_total_bq = _to_float(activity_raw)
        radionuclides: dict[str, dict[str, Any]] = {}
        for radionuclide, col in radionuclide_columns.items():
            raw_value = sheet.cell_value(row_index, col)
            value = _to_float(raw_value)
            censored = _is_mda_marker(raw_value)
            missing_value = raw_value in ("", None)
            status = "detectado" if value is not None else "censurado" if censored else "ausente"
            radionuclides[radionuclide] = {
                "value": value,
                "raw_text": _raw_text(raw_value),
                "status": status,
                "censored": censored,
                "missing": missing_value,
            }

        records.append(
            {
                "row": row_index + 1,
                "sample_id": sample_id,
                "group": group,
                "date": date_text,
                "activity_total_bq": activity_total_bq,
                "activity_total_raw_text": _raw_text(activity_raw),
                "activity_total_censored": _is_mda_marker(activity_raw),
                "activity_total_missing": activity_raw in ("", None),
                "radionuclides": radionuclides,
            }
        )

    return {
        "path": str(activity_path),
        "sheet": sheet.name,
        "headers": headers,
        "records": records,
    }


def _scenario_row_by_radionuclide(scenario: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["radionuclide"]: row for row in scenario.get("rows") or []}


def _scenario_compartment_multipliers(scenario_row: dict[str, Any]) -> dict[str, float | None]:
    compartments = scenario_row.get("compartments") or {}
    water_value = (compartments.get("water") or {}).get("value")
    multipliers: dict[str, float | None] = {"water": 1.0}
    for compartment in COMPARTMENTS:
        key = compartment["key"]
        if key == "water":
            continue
        value = (compartments.get(key) or {}).get("value")
        multipliers[key] = (float(value) / float(water_value)) if value is not None and water_value not in (None, 0) else None
    return multipliers


def _group_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        group: [record for record in records if record.get("group") == group]
        for group in EMPIRICAL_ACTIVITY_GROUPS
    }


def _reference_summary(values: list[float], reference: float | None) -> dict[str, Any]:
    stats_summary = _summary_stats(values)
    p95 = stats_summary.get("p95")
    ratio = p95 / reference if p95 is not None and reference is not None and reference > 0 else None
    exceedance_count = sum(1 for value in values if reference is not None and reference > 0 and value > reference)
    exceedance_rate = exceedance_count / len(values) if values and reference is not None and reference > 0 else None
    return {
        "reference": reference,
        "reference_text": _format_scientific(reference),
        "p95_ratio": ratio,
        "p95_ratio_text": _format_decimal(ratio),
        "status": "sem referência" if ratio is None else "abaixo" if ratio <= 1.0 else "acima",
        "exceedance_count": exceedance_count if exceedance_rate is not None else None,
        "exceedance_rate": exceedance_rate,
        "exceedance_rate_text": _format_percent(exceedance_rate),
    }


def _empirical_group_summaries(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for group, records in grouped.items():
        activity_values = [record["activity_total_bq"] for record in records if record.get("activity_total_bq") is not None]
        stats_summary = _stats_summary_with_text(activity_values)
        summaries.append(
            {
                "group": group,
                "sample_count": len(records),
                "activity_detected_count": len(activity_values),
                "activity_censored_count": sum(1 for record in records if record.get("activity_total_censored")),
                "activity_missing_count": sum(1 for record in records if record.get("activity_total_missing")),
                "activity_unit": "Bq",
                "activity_stats": stats_summary,
                "activity_mean_text": stats_summary["mean_text"],
                "activity_median_text": stats_summary["median_text"],
                "activity_p95_text": stats_summary["p95_text"],
            }
        )
    return summaries


def _empirical_radionuclide_rows(
    grouped: dict[str, list[dict[str, Any]]],
    modeled_radionuclides: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, records in grouped.items():
        for radionuclide in EMPIRICAL_ACTIVITY_RADIONUCLIDES:
            values = [
                record["radionuclides"][radionuclide]["value"]
                for record in records
                if record["radionuclides"][radionuclide]["value"] is not None
            ]
            censored_count = sum(1 for record in records if record["radionuclides"][radionuclide]["censored"])
            missing_count = sum(1 for record in records if record["radionuclides"][radionuclide]["missing"])
            detected_count = len(values)
            sample_count = len(records)
            stats_summary = _stats_summary_with_text(values)
            rows.append(
                {
                    "group": group,
                    "radionuclide": radionuclide,
                    "unit": "Bq/kg",
                    "sample_count": sample_count,
                    "detected_count": detected_count,
                    "censored_count": censored_count,
                    "missing_count": missing_count,
                    "detected_rate": detected_count / sample_count if sample_count else None,
                    "detected_rate_text": _format_percent(detected_count / sample_count if sample_count else None),
                    "model_status": "modelado" if radionuclide in modeled_radionuclides else "observado não modelado",
                    **stats_summary,
                }
            )
    return rows


def _empirical_modeled_compartment_rows(
    scenario: dict[str, Any],
    grouped: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    scenario_rows = _scenario_row_by_radionuclide(scenario)
    flow = (scenario.get("totals") or {}).get("circulation_flow_m3_year") or DEFAULT_DILUTION_FLOW_M3_YEAR
    sample_values: dict[tuple[str, str, str], list[float]] = {}
    for group in EMPIRICAL_ACTIVITY_GROUPS:
        for radionuclide in scenario_rows:
            for compartment in COMPARTMENTS:
                sample_values[(group, radionuclide, compartment["key"])] = []

    for group, records in grouped.items():
        for record in records:
            total_activity = record.get("activity_total_bq")
            detected_sum = sum(
                float(data["value"])
                for data in record.get("radionuclides", {}).values()
                if data.get("value") is not None and data["value"] > 0
            )
            if total_activity is None or total_activity <= 0 or detected_sum <= 0 or flow <= 0:
                continue
            for radionuclide, data in record.get("radionuclides", {}).items():
                detected_value = data.get("value")
                if detected_value is None or detected_value <= 0 or radionuclide not in scenario_rows:
                    continue
                fraction = float(detected_value) / detected_sum
                activity_bq = float(total_activity) * fraction
                water_value = activity_bq / float(flow)
                multipliers = _scenario_compartment_multipliers(scenario_rows[radionuclide])
                for compartment in COMPARTMENTS:
                    multiplier = multipliers.get(compartment["key"])
                    if multiplier is None:
                        continue
                    sample_values[(group, radionuclide, compartment["key"])].append(water_value * multiplier)

    rows: list[dict[str, Any]] = []
    for group in EMPIRICAL_ACTIVITY_GROUPS:
        for radionuclide in EXPECTED_RADIONUCLIDES:
            scenario_row = scenario_rows.get(radionuclide)
            if not scenario_row:
                continue
            for compartment in COMPARTMENTS:
                key = compartment["key"]
                values = sample_values.get((group, radionuclide, key), [])
                stats_summary = _stats_summary_with_text(values)
                base_data = scenario_row["compartments"][key]
                report = _reference_summary(values, base_data.get("report_level"))
                lld = _reference_summary(values, base_data.get("lld"))
                rows.append(
                    {
                        "group": group,
                        "radionuclide": radionuclide,
                        "compartment_key": key,
                        "compartment": compartment["label"],
                        "unit": compartment["unit"],
                        **stats_summary,
                        "report_level": report["reference"],
                        "report_level_text": report["reference_text"],
                        "report_level_p95_ratio": report["p95_ratio"],
                        "report_level_p95_ratio_text": report["p95_ratio_text"],
                        "report_level_status": report["status"],
                        "report_level_exceedance_count": report["exceedance_count"],
                        "report_level_exceedance_rate": report["exceedance_rate"],
                        "report_level_exceedance_rate_text": report["exceedance_rate_text"],
                        "lld": lld["reference"],
                        "lld_text": lld["reference_text"],
                        "lld_p95_ratio": lld["p95_ratio"],
                        "lld_p95_ratio_text": lld["p95_ratio_text"],
                        "lld_status": lld["status"],
                        "lld_exceedance_count": lld["exceedance_count"],
                        "lld_exceedance_rate": lld["exceedance_rate"],
                        "lld_exceedance_rate_text": lld["exceedance_rate_text"],
                    }
                )
    return rows


def _build_empirical_activity_statistics(
    scenario: dict[str, Any],
    *,
    activity_workbook_path: str | Path,
) -> dict[str, Any]:
    loaded = _load_empirical_activity_records(activity_workbook_path)
    records = loaded["records"]
    grouped = _group_records(records)
    modeled_radionuclides = set(_scenario_row_by_radionuclide(scenario))
    unmodeled_radionuclides = [
        radionuclide
        for radionuclide in EMPIRICAL_ACTIVITY_RADIONUCLIDES
        if radionuclide not in modeled_radionuclides
    ]
    group_summaries = _empirical_group_summaries(grouped)
    radionuclide_rows = _empirical_radionuclide_rows(grouped, modeled_radionuclides)
    modeled_compartment_rows = _empirical_modeled_compartment_rows(scenario, grouped)
    group_counts = {summary["group"]: summary["sample_count"] for summary in group_summaries}
    narrative_text = (
        "A estatística empírica usa as medições reais de atividade total TAR de 2019 a 2023, separando TAR - Afluente "
        "e TAR - Efluente. Valores marcados como < MDA> são tratados como censurados: entram nas contagens de não "
        "detectados, mas não entram como valor numérico. Para cada amostra com A-TAR numérico, a fração Si foi calculada "
        "a partir dos radionuclídeos detectados e aplicada à atividade total; em seguida, foram reutilizados a vazão e "
        "os fatores de água, peixe, invertebrado e sedimento da planilha TAR selecionada."
    )
    return {
        "synthetic": False,
        "source_workbook_path": loaded["path"],
        "source_sheet": loaded["sheet"],
        "source_note": "Dados reais de atividade total TAR; < MDA> tratado como dado censurado.",
        "mda_policy": "< MDA> não é convertido para zero nem MDA/2; é contado como censurado e excluído dos cálculos numéricos.",
        "groups": group_summaries,
        "group_counts": group_counts,
        "observed_radionuclides": EMPIRICAL_ACTIVITY_RADIONUCLIDES,
        "modeled_radionuclides": [radionuclide for radionuclide in EXPECTED_RADIONUCLIDES if radionuclide in modeled_radionuclides],
        "unmodeled_radionuclides": unmodeled_radionuclides,
        "radionuclide_rows": radionuclide_rows,
        "modeled_compartment_rows": modeled_compartment_rows,
        "narrative_text": narrative_text,
        "cards": [
            {"label": "Amostras afluente", "value": _format_count(group_counts.get("TAR - Afluente", 0))},
            {"label": "Amostras efluente", "value": _format_count(group_counts.get("TAR - Efluente", 0))},
            {"label": "Política MDA", "value": "censurado"},
            {"label": "Observado não modelado", "value": ", ".join(unmodeled_radionuclides) or "—"},
        ],
    }


def _synthetic_replicates(base_value: float | None, count: int, rng: random.Random) -> list[float]:
    if base_value is None or base_value <= 0:
        return []
    sigma = 0.20
    mu = math.log(base_value) - (sigma * sigma / 2.0)
    return [rng.lognormvariate(mu, sigma) for _ in range(count)]


def _reference_test(values: list[float], reference: float | None, reference_label: str, dataset_label: str) -> dict[str, Any]:
    if not values or reference is None or reference <= 0:
        return {
            "applicable": False,
            "test_label": "Não aplicável",
            "reason": f"Sem {reference_label} numérico para {dataset_label}.",
        }
    ratios = [value / reference for value in values if value > 0]
    if len(ratios) < 3:
        return {
            "applicable": False,
            "test_label": "Não aplicável",
            "reason": "Menos de 3 replicações sintéticas exploratórias válidas.",
            "n": len(ratios),
        }

    log_ratios = [math.log(ratio) for ratio in ratios]
    shapiro_w = None
    shapiro_p = None
    try:
        shapiro = stats.shapiro(log_ratios)
        shapiro_w = float(shapiro.statistic)
        shapiro_p = float(shapiro.pvalue)
    except Exception:
        pass

    normality_met = shapiro_p is not None and shapiro_p >= 0.05
    if normality_met:
        test_label = "Teste t unilateral de uma amostra"
        try:
            test = stats.ttest_1samp(log_ratios, popmean=0.0, alternative="less")
            statistic = float(test.statistic)
            p_value = float(test.pvalue)
        except Exception:
            statistic = None
            p_value = None
    else:
        test_label = "Wilcoxon unilateral de uma amostra"
        try:
            test = stats.wilcoxon(log_ratios, alternative="less", zero_method="pratt")
            statistic = float(test.statistic)
            p_value = float(test.pvalue)
        except Exception:
            statistic = None
            p_value = None

    ratio_summary = _stats_summary_with_text(ratios)
    exceedance_count = sum(1 for ratio in ratios if ratio > 1.0)
    conclusion = (
        f"{dataset_label} ficou abaixo de {reference_label} nas replicações sintéticas exploratórias"
        if p_value is not None and p_value < 0.05 and (ratio_summary["p95"] or 0) < 1.0
        else f"{dataset_label} não sustenta margem estatística exploratória abaixo de {reference_label}"
    )
    return {
        "applicable": p_value is not None,
        "n": len(ratios),
        "test_label": test_label,
        "statistic": statistic,
        "statistic_text": _stat_text(statistic),
        "p_value": p_value,
        "p_value_text": _format_p_value(p_value),
        "shapiro_w": shapiro_w,
        "shapiro_p": shapiro_p,
        "shapiro_p_text": _format_p_value(shapiro_p),
        "normality_met": normality_met,
        "ratio_summary": ratio_summary,
        "p95_ratio": ratio_summary["p95"],
        "p95_ratio_text": _stat_text(ratio_summary["p95"]),
        "exceedance_count": exceedance_count,
        "exceedance_rate": exceedance_count / len(ratios) if ratios else None,
        "exceedance_rate_text": _format_percent(exceedance_count / len(ratios) if ratios else None),
        "conclusion": conclusion,
    }


def _paired_calculated_erica_test(calculated_values: list[float], erica_values: list[float]) -> dict[str, Any]:
    pairs = [
        (calculated, erica)
        for calculated, erica in zip(calculated_values, erica_values)
        if calculated > 0 and erica > 0
    ]
    if len(pairs) < 3:
        return {
            "applicable": False,
            "test_label": "Não aplicável",
            "reason": "Menos de 3 pares sintéticos exploratórios válidos.",
            "n": len(pairs),
        }
    log_ratios = [math.log(calculated / erica) for calculated, erica in pairs]
    shapiro_w = None
    shapiro_p = None
    try:
        shapiro = stats.shapiro(log_ratios)
        shapiro_w = float(shapiro.statistic)
        shapiro_p = float(shapiro.pvalue)
    except Exception:
        pass
    normality_met = shapiro_p is not None and shapiro_p >= 0.05
    if normality_met:
        test_label = "Teste t pareado sobre log(calculado/ERICA)"
        try:
            test = stats.ttest_1samp(log_ratios, popmean=0.0, alternative="two-sided")
            statistic = float(test.statistic)
            p_value = float(test.pvalue)
        except Exception:
            statistic = None
            p_value = None
    else:
        test_label = "Wilcoxon pareado sobre log(calculado/ERICA)"
        try:
            test = stats.wilcoxon(log_ratios, alternative="two-sided", zero_method="pratt")
            statistic = float(test.statistic)
            p_value = float(test.pvalue)
        except Exception:
            statistic = None
            p_value = None

    mean_log = statistics.fmean(log_ratios)
    stdev_log = statistics.stdev(log_ratios) if len(log_ratios) > 1 else 0.0
    ci_half_width = 1.96 * stdev_log / math.sqrt(len(log_ratios)) if len(log_ratios) > 1 else 0.0
    ratios = [math.exp(value) for value in log_ratios]
    return {
        "applicable": p_value is not None,
        "n": len(log_ratios),
        "test_label": test_label,
        "statistic": statistic,
        "statistic_text": _stat_text(statistic),
        "p_value": p_value,
        "p_value_text": _format_p_value(p_value),
        "shapiro_w": shapiro_w,
        "shapiro_p": shapiro_p,
        "shapiro_p_text": _format_p_value(shapiro_p),
        "normality_met": normality_met,
        "mean_log_ratio": mean_log,
        "mean_log_ratio_text": _stat_text(mean_log),
        "mean_ratio": math.exp(mean_log),
        "mean_ratio_text": _stat_text(math.exp(mean_log)),
        "median_ratio": statistics.median(ratios),
        "median_ratio_text": _stat_text(statistics.median(ratios)),
        "ci95_low": math.exp(mean_log - ci_half_width),
        "ci95_low_text": _stat_text(math.exp(mean_log - ci_half_width)),
        "ci95_high": math.exp(mean_log + ci_half_width),
        "ci95_high_text": _stat_text(math.exp(mean_log + ci_half_width)),
        "conclusion": "Comparação exploratória entre cálculo por fórmula e ERICA Tool; não constitui validação regulatória final.",
    }


def _erica_value(radionuclide: str, compartment_key: str) -> float | None:
    return (ERICA_TOOL_VALUES.get(radionuclide) or {}).get(compartment_key)


def _build_statistical_comparison(scenario: dict[str, Any], *, sample_count: int, seed: int) -> dict[str, Any]:
    calculated_rows: list[dict[str, Any]] = []
    erica_rows: list[dict[str, Any]] = []
    norm_rows: list[dict[str, Any]] = []
    descriptive_rows: list[dict[str, Any]] = []
    inferential_rows: list[dict[str, Any]] = []
    paired_comparison_rows: list[dict[str, Any]] = []

    for row in scenario.get("rows") or []:
        radionuclide = row["radionuclide"]
        for compartment in COMPARTMENTS:
            key = compartment["key"]
            data = row["compartments"][key]
            calculated_value = data.get("value")
            erica_value = _erica_value(radionuclide, key)
            calculated_rows.append(
                {
                    "dataset": "calculado",
                    "radionuclide": radionuclide,
                    "compartment_key": key,
                    "compartment": compartment["label"],
                    "unit": compartment["unit"],
                    "value": calculated_value,
                    "value_text": _format_scientific(calculated_value),
                    "method": "Fórmulas de transporte/incorporação da planilha TAR",
                }
            )
            erica_rows.append(
                {
                    "dataset": "ERICA Tool",
                    "radionuclide": radionuclide,
                    "compartment_key": key,
                    "compartment": compartment["label"],
                    "unit": compartment["unit"],
                    "value": erica_value,
                    "value_text": _format_scientific(erica_value),
                    "method": "ERICA Tool Nível 2; valores extraídos do PDF corrigido",
                }
            )
            for reference_key, reference_label in (("report_level", "Report Level"), ("lld", "LLD")):
                reference_value = data.get(reference_key)
                if reference_value is None:
                    continue
                norm_rows.append(
                    {
                        "radionuclide": radionuclide,
                        "compartment_key": key,
                        "compartment": compartment["label"],
                        "reference": reference_label,
                        "unit": compartment["unit"],
                        "value": reference_value,
                        "value_text": _format_scientific(reference_value),
                    }
                )

            for dataset_key, dataset_label, base_value in (
                ("calculado", "Calculado por fórmulas", calculated_value),
                ("erica", "Simulado pelo ERICA Tool", erica_value),
            ):
                rng = random.Random(f"{seed}:{scenario.get('key')}:{radionuclide}:{key}:{dataset_key}")
                replicates = _synthetic_replicates(base_value, sample_count, rng)
                if replicates:
                    descriptive_rows.append(
                        {
                            "dataset": dataset_label,
                            "radionuclide": radionuclide,
                            "compartment_key": key,
                            "compartment": compartment["label"],
                            "unit": compartment["unit"],
                            "base_value": base_value,
                            "base_value_text": _format_scientific(base_value),
                            **_stats_summary_with_text(replicates),
                        }
                    )
                for reference_key, reference_label in (("report_level", "Report Level"), ("lld", "LLD")):
                    reference_value = data.get(reference_key)
                    if reference_value is None or not replicates:
                        continue
                    test_result = _reference_test(replicates, reference_value, reference_label, dataset_label)
                    test_result.update(
                        {
                            "dataset": dataset_label,
                            "radionuclide": radionuclide,
                            "compartment_key": key,
                            "compartment": compartment["label"],
                            "reference": reference_label,
                            "reference_value": reference_value,
                            "reference_value_text": _format_scientific(reference_value),
                        }
                    )
                    inferential_rows.append(test_result)

            calculated_rng = random.Random(f"{seed}:{scenario.get('key')}:{radionuclide}:{key}:paired:calculated")
            erica_rng = random.Random(f"{seed}:{scenario.get('key')}:{radionuclide}:{key}:paired:erica")
            calculated_replicates = _synthetic_replicates(calculated_value, sample_count, calculated_rng)
            erica_replicates = _synthetic_replicates(erica_value, sample_count, erica_rng)
            if calculated_replicates and erica_replicates:
                paired = _paired_calculated_erica_test(calculated_replicates, erica_replicates)
                paired.update(
                    {
                        "radionuclide": radionuclide,
                        "compartment_key": key,
                        "compartment": compartment["label"],
                        "unit": compartment["unit"],
                        "calculated_value": calculated_value,
                        "calculated_value_text": _format_scientific(calculated_value),
                        "erica_value": erica_value,
                        "erica_value_text": _format_scientific(erica_value),
                    }
                )
                paired_comparison_rows.append(paired)

    narrative_text = (
        f"A análise estatística usa {sample_count} replicações sintéticas exploratórias por valor base, com seed {seed}. "
        "Os dados calculados vêm das fórmulas de transporte/incorporação da planilha TAR; os dados simulados vêm do "
        "ERICA Tool Nível 2; Report Level e LLD permanecem como referências normativas fixas. As replicações não são "
        "medições reais e não sustentam conclusão regulatória isolada."
    )
    return {
        "sample_count": sample_count,
        "seed": seed,
        "synthetic": True,
        "source_note": "replicações sintéticas exploratórias geradas para análise estatística; não são medições reais.",
        "erica_source": "Artigo TAR1 correção.pdf, tabela/screenshot do ERICA Tool Nível 2.",
        "calculated_rows": calculated_rows,
        "erica_rows": erica_rows,
        "norm_rows": norm_rows,
        "descriptive_rows": descriptive_rows,
        "inferential_rows": inferential_rows,
        "paired_comparison_rows": paired_comparison_rows,
        "narrative_text": narrative_text,
    }


def _run_one_sample_limit_test(values: list[float], report_level: float | None) -> dict[str, Any]:
    if not values or report_level is None or report_level <= 0:
        return {
            "applicable": False,
            "test_label": "Não aplicável",
            "reason": "Sem Report Level numérico para comparação inferencial.",
        }
    ratios = [value / report_level for value in values if value is not None and value > 0]
    if len(ratios) < 3:
        return {
            "applicable": False,
            "test_label": "Não aplicável",
            "reason": "Menos de 3 simulações válidas para triagem de normalidade.",
            "n": len(ratios),
        }

    log_ratios = [math.log(ratio) for ratio in ratios]
    shapiro_w = None
    shapiro_p = None
    try:
        shapiro_w, shapiro_p = stats.shapiro(log_ratios)
        shapiro_w = float(shapiro_w)
        shapiro_p = float(shapiro_p)
    except Exception:
        shapiro_w = None
        shapiro_p = None

    normality_met = shapiro_p is not None and shapiro_p >= 0.05
    if normality_met:
        test_label = "Teste t unilateral de uma amostra"
        try:
            result = stats.ttest_1samp(log_ratios, popmean=0.0, alternative="less")
            statistic = float(result.statistic)
            p_value = float(result.pvalue)
        except Exception:
            statistic = None
            p_value = None
    else:
        test_label = "Wilcoxon unilateral de uma amostra"
        try:
            result = stats.wilcoxon(log_ratios, alternative="less", zero_method="pratt")
            statistic = float(result.statistic)
            p_value = float(result.pvalue)
        except Exception:
            statistic = None
            p_value = None

    exceedance_count = sum(1 for ratio in ratios if ratio > 1.0)
    stats_summary = _summary_stats(ratios)
    p95_ratio = stats_summary["p95"]
    significant_below = p_value is not None and p_value < 0.05 and p95_ratio is not None and p95_ratio < 1.0
    if significant_below and exceedance_count == 0:
        conclusion = "as simulações permaneceram estatisticamente abaixo do Report Level"
    elif significant_below:
        conclusion = "a tendência central ficou abaixo do Report Level, mas houve simulações acima da referência"
    elif p_value is None:
        conclusion = "o teste selecionado não produziu p-value válido"
    else:
        conclusion = "não houve evidência estatística suficiente para afirmar margem abaixo do Report Level"

    return {
        "applicable": p_value is not None,
        "n": len(ratios),
        "test_label": test_label,
        "statistic": statistic,
        "p_value": p_value,
        "p_value_text": _format_p_value(p_value),
        "shapiro_w": shapiro_w,
        "shapiro_p": shapiro_p,
        "shapiro_p_text": _format_p_value(shapiro_p),
        "normality_met": normality_met,
        "p95_ratio": p95_ratio,
        "p95_ratio_text": f"{p95_ratio:.4f}".replace(".", ",") if p95_ratio is not None else "—",
        "exceedance_count": exceedance_count,
        "exceedance_rate": exceedance_count / len(ratios) if ratios else None,
        "conclusion": conclusion,
    }


def _build_hypothetical_test_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in rows:
        for compartment in COMPARTMENTS:
            data = row["compartments"][compartment["key"]]
            report_level = data.get("report_level")
            simulated_values = data.get("simulated_values") or []
            if report_level is None:
                continue
            result = _run_one_sample_limit_test(simulated_values, report_level)
            result.update(
                {
                    "radionuclide": row["radionuclide"],
                    "compartment": compartment["label"],
                    "unit": compartment["unit"],
                    "report_level": report_level,
                    "report_level_text": data.get("report_level_text"),
                    "p95_value": data.get("value"),
                    "p95_value_text": data.get("value_text"),
                }
            )
            results.append(result)
    return results


def _build_hypothetical_statistical_text(test_results: list[dict[str, Any]], measurement_count: int) -> str:
    applicable = [result for result in test_results if result.get("applicable")]
    if not applicable:
        return (
            "O cenário hipotético gerou medições sintéticas, mas não encontrou pares suficientes de simulação e "
            "Report Level para aplicar teste inferencial."
        )
    test_labels = sorted({str(result.get("test_label")) for result in applicable})
    significant = [result for result in applicable if result.get("p_value") is not None and result.get("p_value") < 0.05]
    exceeded = [result for result in applicable if int(result.get("exceedance_count") or 0) > 0]
    if len(significant) == len(applicable) and not exceeded:
        closing = "Todos os contrastes com Report Level ficaram estatisticamente abaixo da referência, sem simulações acima do limite."
    elif significant:
        closing = "Parte dos contrastes ficou estatisticamente abaixo da referência; os casos com simulações acima do limite devem ser avaliados individualmente."
    else:
        closing = "Os testes não sustentaram evidência estatística suficiente de margem abaixo do Report Level."
    return (
        f"O cenário hipotético gerou {measurement_count} medições sintéticas de espectrometria gama para cada radionuclídeo da água do TAR. "
        "Cada medição alimentou a simulação dos compartimentos ambientais, preservando a relação entre valor medido e resultado simulado. "
        "A comparação inferencial foi feita sobre o logaritmo da razão simulado/Report Level. "
        "O Shapiro-Wilk avaliou a normalidade dessas razões; quando a normalidade foi atendida, aplicou-se teste t unilateral de uma amostra, "
        "e, quando não foi atendida, aplicou-se Wilcoxon unilateral de uma amostra. "
        f"Os testes utilizados foram: {', '.join(test_labels)}. {closing}"
    )


def _hypothetical_scenario_summary(
    base_scenario: dict[str, Any],
    *,
    measurement_count: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for base_row in base_scenario["rows"]:
        source_base = base_row.get("source_concentration_bq_m3")
        if source_base is None or source_base <= 0:
            continue
        measurements = _generate_positive_measurements(source_base, measurement_count, rng)
        measurement_summary = _summary_stats(measurements)
        generated_row: dict[str, Any] = {
            "row": base_row.get("row"),
            "radionuclide": base_row["radionuclide"],
            "source_concentration_bq_m3": source_base,
            "source_concentration_bq_m3_text": _format_scientific(source_base),
            "measurement_count": measurement_count,
            "measurements_bq_m3": measurements,
            "measurement_summary": {
                **measurement_summary,
                "mean_text": _format_scientific(measurement_summary["mean"]),
                "median_text": _format_scientific(measurement_summary["median"]),
                "p95_text": _format_scientific(measurement_summary["p95"]),
                "min_text": _format_scientific(measurement_summary["min"]),
                "max_text": _format_scientific(measurement_summary["max"]),
            },
            "compartments": {},
        }
        for compartment in COMPARTMENTS:
            base_data = base_row["compartments"][compartment["key"]]
            base_value = base_data.get("value")
            simulated_values = [
                base_value * (measurement / source_base)
                for measurement in measurements
                if base_value is not None
            ]
            simulated_summary = _summary_stats(simulated_values)
            p95_value = simulated_summary["p95"]
            report_result = _ratio_status(p95_value, base_data.get("report_level"))
            lld_result = _ratio_status(p95_value, base_data.get("lld"))
            generated_row["compartments"][compartment["key"]] = {
                "label": compartment["label"],
                "unit": compartment["unit"],
                "value": p95_value,
                "value_text": _format_scientific(p95_value),
                "display_statistic": "P95",
                "simulated_values": simulated_values,
                "simulated_summary": {
                    **simulated_summary,
                    "mean_text": _format_scientific(simulated_summary["mean"]),
                    "median_text": _format_scientific(simulated_summary["median"]),
                    "p95_text": _format_scientific(simulated_summary["p95"]),
                    "min_text": _format_scientific(simulated_summary["min"]),
                    "max_text": _format_scientific(simulated_summary["max"]),
                },
                "report_level": report_result["reference"],
                "report_level_text": _format_scientific(report_result["reference"]),
                "report_level_ratio": report_result["ratio"],
                "report_level_ratio_text": f"{report_result['ratio']:.4f}".replace(".", ",") if report_result["ratio"] is not None else "—",
                "report_level_status": report_result["status"],
                "lld": lld_result["reference"],
                "lld_text": _format_scientific(lld_result["reference"]),
                "lld_ratio": lld_result["ratio"],
                "lld_ratio_text": f"{lld_result['ratio']:.4f}".replace(".", ",") if lld_result["ratio"] is not None else "—",
                "lld_status": lld_result["status"],
            }
        rows.append(generated_row)

    reference_counts = _build_reference_counts(rows)
    report_level_exceedances = _build_exceedances(rows, reference="Report Level")
    lld_exceedances = _build_exceedances(rows, reference="LLD")
    test_results = _build_hypothetical_test_results(rows)
    totals = dict(base_scenario.get("totals") or {})
    totals["total_water_concentration_bq_m3"] = sum(
        row["compartments"]["water"]["value"] or 0.0
        for row in rows
    )
    return {
        "key": "hipotetico",
        "sheet": "gerado",
        "label": "Cenário hipotético",
        "source_scenario": base_scenario.get("label"),
        "source_sheet": base_scenario.get("sheet"),
        "is_hypothetical": True,
        "seed": seed,
        "measurement_count": measurement_count,
        "radionuclide_count": len(rows),
        "radionuclides": [row["radionuclide"] for row in rows],
        "expected_radionuclides": EXPECTED_RADIONUCLIDES,
        "rows": rows,
        "totals": totals,
        "reference_counts": reference_counts,
        "exceedances": report_level_exceedances,
        "report_level_exceedances": report_level_exceedances,
        "lld_exceedances": lld_exceedances,
        "has_reference_exceedance": bool(report_level_exceedances),
        "has_lld_exceedance": bool(lld_exceedances),
        "statistical_tests": test_results,
        "statistical_text": _build_hypothetical_statistical_text(test_results, measurement_count),
    }


def _inferential_assessment() -> dict[str, Any]:
    return {
        "applicable": False,
        "status": "teste inferencial não aplicável",
        "reason": (
            "A planilha TAR contém resultados calculados por modelo determinístico. O n = 8 representa radionuclídeos, "
            "não amostras ambientais independentes nem réplicas por matriz."
        ),
        "current_n": 8,
        "sample_unit": "radionuclídeo calculado",
        "recommended_action": (
            "Para inferência estatística, registrar medições ambientais reais com réplicas por compartimento, "
            "radionuclídeo, cenário e período de coleta."
        ),
        "minimums": INFERENTIAL_TEST_MINIMUMS,
    }


def load_tar_workbook_model(
    workbook_path: str | Path,
    *,
    hypothetical_n: int = 60,
    hypothetical_seed: int = 20260504,
) -> dict[str, Any]:
    path = Path(workbook_path)
    if not path.exists():
        raise TarWorkbookError(f"Planilha TAR não encontrada: {path}")
    try:
        workbook = openpyxl.load_workbook(path, data_only=True, read_only=False)
    except Exception as exc:
        raise TarWorkbookError(f"Não foi possível abrir a planilha TAR: {exc}") from exc
    try:
        scenarios: dict[str, Any] = {}
        for scenario_key, spec in SCENARIOS.items():
            sheet_name = spec["sheet"]
            if not sheet_name:
                continue
            if sheet_name not in workbook.sheetnames:
                raise TarWorkbookError(f"A aba obrigatória {sheet_name!r} não foi encontrada na planilha TAR.")
            scenarios[scenario_key] = _scenario_summary(scenario_key, workbook[sheet_name])
        scenarios["hipotetico"] = _hypothetical_scenario_summary(
            scenarios["a1_a2"],
            measurement_count=hypothetical_n,
            seed=hypothetical_seed,
        )
        return {
            "workbook_path": str(path),
            "scenarios": scenarios,
            "inferential_assessment": _inferential_assessment(),
        }
    finally:
        workbook.close()


def build_tar_summary(
    workbook_path: str | Path,
    scenario: Any = "a1",
    *,
    activity_workbook_path: str | Path | None = None,
    hypothetical_n: Any = 60,
    hypothetical_seed: Any = 20260504,
    sensitivity_n: Any = DEFAULT_SENSITIVITY_N,
    sensitivity_seed: Any = DEFAULT_SENSITIVITY_SEED,
    stat_n: Any = DEFAULT_STAT_N,
    stat_seed: Any = DEFAULT_STAT_SEED,
) -> dict[str, Any]:
    resolved_n = _safe_int(hypothetical_n, 60, minimum=10, maximum=500)
    resolved_seed = _safe_int(hypothetical_seed, 20260504, minimum=1, maximum=999999999)
    resolved_sensitivity_n = _safe_int(sensitivity_n, DEFAULT_SENSITIVITY_N, minimum=100, maximum=50000)
    resolved_sensitivity_seed = _safe_int(sensitivity_seed, DEFAULT_SENSITIVITY_SEED, minimum=1, maximum=999999999)
    resolved_stat_n = _safe_int(stat_n, DEFAULT_STAT_N, minimum=10, maximum=5000)
    resolved_stat_seed = _safe_int(stat_seed, DEFAULT_STAT_SEED, minimum=1, maximum=999999999)
    model = load_tar_workbook_model(
        workbook_path,
        hypothetical_n=resolved_n,
        hypothetical_seed=resolved_seed,
    )
    scenario_key = resolve_tar_scenario_key(scenario)
    scenario_model = dict(model["scenarios"][scenario_key])
    scenario_model["sensitivity"] = _build_sensitivity_analysis(
        scenario_model,
        sample_count=resolved_sensitivity_n,
        seed=resolved_sensitivity_seed,
    )
    scenario_model["statistical_comparison"] = _build_statistical_comparison(
        scenario_model,
        sample_count=resolved_stat_n,
        seed=resolved_stat_seed,
    )
    resolved_activity_path = _empirical_activity_path(workbook_path, activity_workbook_path)
    scenario_model["empirical_activity_statistics"] = _build_empirical_activity_statistics(
        scenario_model,
        activity_workbook_path=resolved_activity_path,
    )
    return {
        "ok": True,
        "workbook_path": model["workbook_path"],
        "activity_workbook_path": str(resolved_activity_path),
        "selected_scenario": scenario_key,
        "available_scenarios": [
            {"key": key, "label": value["label"], "sheet": value["sheet"]}
            for key, value in SCENARIOS.items()
        ],
        "scenario": scenario_model,
        "inferential_assessment": model["inferential_assessment"],
    }
