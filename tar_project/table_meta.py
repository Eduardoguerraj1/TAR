from __future__ import annotations

from typing import Any


TAR_TABLES: dict[str, dict[str, Any]] = {
    "reference_counts": {
        "number": 1,
        "caption": "Referências normativas disponíveis por compartimento",
        "lead_text": (
            "A {table} reúne as referências disponíveis para água, peixe, invertebrado e sedimento. "
            "Os dados indicam quais compartimentos podem ser comparados diretamente com Report Level e LLD. "
            "Assim, a leitura separa resultados avaliáveis daqueles classificados como sem referência normativa."
        ),
        "column_notes": [
            "Compartimento: matriz ambiental avaliada no modelo TAR.",
            "Report Level: quantidade de referências de notificação disponíveis para o compartimento.",
            "LLD: quantidade de referências de detecção disponíveis para o compartimento.",
            "Radionuclídeos com referência: radionuclídeos que têm Report Level cadastrado naquele compartimento.",
        ],
        "unit_note": "Contagens em número de radionuclídeos com referência cadastrada.",
    },
    "concentrations": {
        "number": 2,
        "caption": "Concentrações calculadas por radionuclídeo e compartimento",
        "lead_text": (
            "A {table} apresenta as concentrações calculadas para cada radionuclídeo do cenário selecionado. "
            "Os valores mostram a transferência do resultado da água para peixe, invertebrado e sedimento. "
            "Assim, a tabela fixa a base numérica usada nas comparações regulatórias posteriores."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo avaliado na planilha TAR.",
            "Água: concentração calculada na água do mar, em Bq/m³.",
            "Peixe: concentração calculada no peixe, em Bq/kg.",
            "Invertebrado: concentração calculada no invertebrado, em Bq/kg.",
            "Sedimento: concentração calculada no sedimento, em Bq/kg.",
        ],
        "unit_note": "As unidades aparecem no cabeçalho de cada compartimento.",
    },
    "reference_results": {
        "number": 3,
        "caption": "Comparação das concentrações com Report Level e LLD",
        "lead_text": (
            "A {table} compara cada concentração calculada com as referências normativas disponíveis. "
            "A razão valor/referência mostra a proximidade em relação ao Report Level e ao LLD; valores acima de 1 indicam superação da referência. "
            "Assim, a tabela identifica onde há margem, ausência de referência ou necessidade de conferência técnica."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo avaliado.",
            "Compartimento: matriz ambiental da comparação.",
            "Concentração: valor calculado pela planilha TAR.",
            "Report Level: nível de notificação usado como referência regulatória.",
            "Razão valor/Report Level: concentração dividida pelo Report Level.",
            "Status Report Level: classificação abaixo, acima ou sem referência.",
            "LLD: referência de detecção cadastrada.",
            "Razão valor/LLD: concentração dividida pelo LLD.",
            "Status LLD: classificação em relação ao LLD.",
        ],
        "unit_note": "Concentração, Report Level e LLD usam a unidade do compartimento avaliado.",
    },
    "hypothetical_measurements": {
        "number": 4,
        "caption": "Resumo das medições sintéticas da água do TAR",
        "lead_text": (
            "A {table} reúne as medições sintéticas geradas para a água do TAR no cenário hipotético. "
            "Os dados indicam a escala da entrada simulada antes da propagação para os compartimentos ambientais. "
            "Assim, a tabela documenta a base usada para calcular o percentil 95 das simulações."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo usado na simulação.",
            "n: número de medições sintéticas geradas.",
            "Valor base TAR: concentração de referência usada para iniciar a simulação, em Bq/m³.",
            "Média medida: média das medições sintéticas, em Bq/m³.",
            "Mediana medida: valor central das medições sintéticas, em Bq/m³.",
            "P95 medido: percentil 95 das medições sintéticas, em Bq/m³.",
        ],
        "unit_note": "P95 é o valor abaixo do qual ficam 95% das simulações ordenadas.",
    },
    "hypothetical_tests": {
        "number": 5,
        "caption": "Teste estatístico das simulações contra o Report Level",
        "lead_text": (
            "A {table} apresenta o teste aplicado às razões simuladas em relação ao Report Level. "
            "O Shapiro-Wilk orienta a escolha entre o teste t unilateral e o Wilcoxon unilateral. "
            "Assim, a tabela mostra se a distribuição simulada sustenta margem estatística abaixo da referência."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo avaliado no teste.",
            "Compartimento: matriz ambiental testada.",
            "n sim.: número de simulações válidas no contraste.",
            "Shapiro-Wilk: p-value do teste de normalidade das razões em log.",
            "Teste usado: teste inferencial selecionado.",
            "p-value: probabilidade associada ao teste unilateral.",
            "P95 simulado / Report Level: razão entre o P95 simulado e a referência.",
            "Acima do limite: número de simulações que superaram o Report Level.",
            "Conclusão: leitura exploratória do resultado.",
        ],
        "unit_note": "Razões e p-values são adimensionais.",
    },
    "empirical_groups": {
        "number": 6,
        "caption": "Resumo por grupo de amostras",
        "lead_text": (
            "A {table} reúne somente as amostras reais do TAR - Afluente usadas na análise. "
            "Os dados indicam a cobertura de A-TAR numérico, valores censurados e registros ausentes nesse grupo. "
            "Assim, a tabela define a base empírica antes do cálculo por radionuclídeo."
        ),
        "column_notes": [
            "Grupo: identificação da amostra como TAR - Afluente.",
            "Amostras: total de registros do grupo.",
            "A-TAR detectado: registros com atividade total numérica.",
            "A-TAR < MDA: registros abaixo do mínimo detectável.",
            "A-TAR ausente: registros sem valor de atividade total.",
            "Média A-TAR: média dos valores numéricos, em Bq.",
            "Mediana A-TAR: valor central dos valores numéricos, em Bq.",
            "P95 A-TAR: percentil 95 dos valores numéricos, em Bq.",
        ],
        "unit_note": "A-TAR é apresentado em Bq.",
    },
    "empirical_radionuclides": {
        "number": 7,
        "caption": "Estatística descritiva por radionuclídeo observado",
        "lead_text": (
            "A {table} resume as medições reais por radionuclídeo e grupo de amostras. "
            "As contagens de detectados, censurados e ausentes mostram a qualidade da base antes de qualquer transformação por fórmula. "
            "Assim, a tabela preserva a diferença entre valor medido e registro menor que MDA."
        ),
        "column_notes": [
            "Grupo: TAR - Afluente.",
            "Radionuclídeo: radionuclídeo medido na planilha empírica.",
            "Status no modelo: indica se o radionuclídeo é modelado pela planilha TAR atual.",
            "Amostras: total de registros do grupo.",
            "Detectados: registros com valor numérico.",
            "< MDA: registros censurados abaixo do mínimo detectável.",
            "Ausentes: registros sem valor.",
            "Taxa detectada: proporção de registros com valor numérico.",
            "Média: média dos valores detectados, em Bq/kg.",
            "Mediana: valor central dos detectados, em Bq/kg.",
            "P95: percentil 95 dos detectados, em Bq/kg.",
        ],
        "unit_note": "Os valores numéricos dos radionuclídeos observados estão em Bq/kg.",
    },
    "empirical_modeled": {
        "number": 8,
        "caption": "Resultados calculados por fórmula a partir das amostras reais",
        "lead_text": (
            "A {table} aplica a fórmula da planilha TAR às amostras reais com A-TAR numérico e radionuclídeos detectados. "
            "Os resultados mostram a faixa calculada por compartimento e sua proximidade ao Report Level. "
            "Assim, a tabela conecta as medições reais à comparação ambiental usada no relatório."
        ),
        "column_notes": [
            "Grupo: TAR - Afluente.",
            "Radionuclídeo: radionuclídeo modelado pela planilha TAR.",
            "Compartimento: água, peixe, invertebrado ou sedimento.",
            "n: número de amostras válidas usadas no cálculo.",
            "Média: média dos resultados calculados.",
            "Mediana: valor central dos resultados calculados.",
            "P95: percentil 95 dos resultados calculados.",
            "Report Level: referência de notificação do compartimento.",
            "P95 / Report Level: razão entre P95 calculado e Report Level.",
            "Status: classificação abaixo, acima ou sem referência.",
            "Freq. > Report Level: proporção de amostras calculadas acima da referência.",
        ],
        "unit_note": "Os resultados usam a unidade do compartimento ambiental.",
    },
    "empirical_inferential": {
        "number": 9,
        "caption": "Inferência com dados reais do TAR - Afluente contra Report Level fixo",
        "lead_text": (
            "A {table} aplica inferência aos resultados calculados por amostra real do TAR - Afluente. "
            "O Report Level é tratado como referência fixa; a incerteza fica na distribuição das amostras calculadas. "
            "Assim, a tabela mostra frequência real de ultrapassagem, IC95% binomial e p-value quando o n permite teste sobre log(valor/referência)."
        ),
        "column_notes": [
            "Grupo: TAR - Afluente.",
            "Radionuclídeo: radionuclídeo modelado pela planilha TAR.",
            "Compartimento: matriz ambiental avaliada.",
            "n: número de amostras reais válidas usadas no contraste.",
            "Report Level: referência fixa de notificação.",
            "P95 razão: percentil 95 da razão valor calculado/Report Level.",
            "Ultrapassagens: número de amostras calculadas acima do Report Level.",
            "Freq. > Report Level: proporção observada de ultrapassagem.",
            "IC95% freq.: intervalo de confiança binomial da frequência de ultrapassagem.",
            "Teste: teste unilateral sobre log(valor/Report Level).",
            "p-value: evidência estatística de valores abaixo do Report Level.",
            "Conclusão: leitura técnica do contraste.",
        ],
        "unit_note": "Razões, frequências, IC95% e p-values são adimensionais.",
    },
    "stat_calculated": {
        "number": 10,
        "caption": "Dados calculados por fórmulas de transporte/incorporação",
        "lead_text": (
            "A {table} reúne os valores determinísticos calculados pela planilha TAR para cada radionuclídeo e compartimento. "
            "Esses valores são mantidos como resultados de fórmula, sem replicações aleatórias. "
            "Assim, a tabela separa o resultado de fórmula dos valores simulados pelo ERICA Tool."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo avaliado.",
            "Compartimento: matriz ambiental calculada.",
            "Valor base: concentração calculada pela planilha.",
            "Unidade: unidade do compartimento.",
            "Origem: método ou fonte do valor.",
        ],
        "unit_note": "A unidade varia conforme o compartimento ambiental.",
    },
    "stat_erica": {
        "number": 11,
        "caption": "Dados simulados pelo ERICA Tool",
        "lead_text": (
            "A {table} apresenta os valores estimados do ERICA Tool para comparação exploratória com a planilha TAR. "
            "A água foi convertida para a mesma unidade usada no modelo TAR quando necessário. "
            "Assim, a tabela mantém separados os resultados de simulação externa e os resultados calculados por fórmula."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo avaliado.",
            "Compartimento: matriz ambiental simulada.",
            "Valor base: valor do ERICA Tool usado na comparação.",
            "Unidade: unidade harmonizada para comparação.",
            "Origem: fonte e ajuste aplicado ao valor.",
        ],
        "unit_note": "A unidade varia conforme o compartimento ambiental.",
    },
    "stat_norms": {
        "number": 12,
        "caption": "Normas: Report Level e LLD",
        "lead_text": (
            "A {table} reúne os valores normativos fixos usados nas comparações. "
            "Report Level e LLD não são amostras aleatórias e não entram na estatística como observações. "
            "Assim, a tabela define as referências contra as quais os resultados calculados e simulados são avaliados."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo com referência cadastrada.",
            "Compartimento: matriz ambiental da referência.",
            "Referência: tipo de valor normativo, Report Level ou LLD.",
            "Valor normativo: valor numérico da referência.",
            "Unidade: unidade associada ao compartimento.",
        ],
        "unit_note": "Report Level é critério de notificação; LLD é referência de detecção.",
    },
    "stat_descriptive": {
        "number": 13,
        "caption": "Estatística descritiva dos valores calculados e estimados",
        "lead_text": (
            "A {table} resume, por compartimento, a dispersão dos valores determinísticos calculados e dos valores estimados pelo ERICA Tool. "
            "Média, mediana, quartis, P95 e CV mostram como os radionuclídeos se distribuem em cada conjunto. "
            "Assim, a tabela mantém estatística descritiva sem criar replicações aleatórias."
        ),
        "column_notes": [
            "Conjunto: origem do valor, calculado por fórmulas ou ERICA Tool.",
            "Radionuclídeo: indica Todos quando a estatística resume os radionuclídeos do compartimento.",
            "Compartimento: matriz ambiental.",
            "n: número de valores por conjunto e compartimento.",
            "Média: média dos valores.",
            "Mediana: valor central dos valores.",
            "Desvio-padrão: dispersão absoluta dos valores.",
            "Q1: primeiro quartil.",
            "Q3: terceiro quartil.",
            "P95: percentil 95.",
            "CV: coeficiente de variação, calculado como desvio-padrão dividido pela média.",
        ],
        "unit_note": "CV é adimensional; as demais estatísticas usam a unidade do compartimento.",
    },
    "stat_inferential": {
        "number": 14,
        "caption": "Estatística inferencial contra Report Level e LLD",
        "lead_text": (
            "A {table} apresenta testes contra referências fixas quando houver amostras válidas para esse contraste. "
            "O p-value indica a evidência estatística exploratória de margem abaixo da referência, enquanto P95 razão mostra a posição conservadora da distribuição. "
            "Assim, a tabela evita confundir significância estatística com conclusão regulatória final."
        ),
        "column_notes": [
            "Conjunto: origem das replicações.",
            "Radionuclídeo: radionuclídeo avaliado.",
            "Compartimento: matriz ambiental.",
            "Norma: referência usada no teste, Report Level ou LLD.",
            "n: número de razões válidas.",
            "Shapiro-Wilk: p-value da normalidade das razões em log.",
            "Teste: teste inferencial selecionado.",
            "p-value: resultado do teste contra a referência.",
            "P95 razão: percentil 95 da razão valor/referência.",
            "Ultrapassagem: proporção de replicações acima da referência.",
            "Conclusão exploratória: interpretação técnica do resultado.",
        ],
        "unit_note": "Razões, p-values e taxas são adimensionais.",
    },
    "stat_paired": {
        "number": 15,
        "caption": "Comparação pareada: calculado por fórmulas vs ERICA Tool",
        "lead_text": (
            "A {table} compara, por par, os resultados calculados pela planilha e os valores estimados do ERICA Tool. "
            "A razão calculado/ERICA mostra se uma fonte tende a ficar acima da outra no mesmo radionuclídeo e compartimento. "
            "Assim, a tabela oferece visualização estatística exploratória sem tratar a comparação como validação regulatória final."
        ),
        "column_notes": [
            "Escopo: todos os compartimentos ou um compartimento específico.",
            "Compartimento: matriz ambiental comparada.",
            "n: número de pares radionuclídeo-compartimento válidos.",
            "Mediana calculado/ERICA: mediana da razão entre as fontes.",
            "IC95% da razão média: intervalo de confiança da razão média em escala original.",
            "Teste: teste aplicado aos logaritmos das razões.",
            "p-value: resultado do teste pareado.",
            "Conclusão: leitura exploratória da comparação.",
        ],
        "unit_note": "Razões e p-values são adimensionais; Calculado e ERICA usam a unidade do compartimento.",
    },
    "sensitivity_variables": {
        "number": 16,
        "caption": "Distribuições sintéticas usadas no Monte Carlo",
        "lead_text": (
            "A {table} define as variáveis sorteadas na análise de sensibilidade. "
            "Os parâmetros mostram quais fatores aumentam ou reduzem os resultados simulados em cada rodada. "
            "Assim, a tabela fixa a base metodológica antes da leitura dos gráficos e resultados do Monte Carlo."
        ),
        "column_notes": [
            "Variável: fator incerto sorteado.",
            "Distribuição: forma estatística usada no sorteio.",
            "Parâmetros: limites, mediana ou valor mais provável usados na distribuição.",
            "Base: valor de referência do cenário.",
            "Unidade: unidade física ou indicação de multiplicador.",
            "Uso no modelo: papel da variável no cálculo.",
        ],
        "unit_note": "Multiplicadores são adimensionais.",
    },
    "sensitivity_influence": {
        "number": 17,
        "caption": "Ranking de influência sobre a maior razão valor simulado / Report Level",
        "lead_text": (
            "A {table} ordena as variáveis pela associação com a maior razão simulada em relação ao Report Level. "
            "A correlação de Spearman mostra o sentido do efeito e o valor absoluto mostra a força relativa. "
            "Assim, a tabela indica quais incertezas mais aproximam os resultados da referência."
        ),
        "column_notes": [
            "Variável: fator sorteado no Monte Carlo.",
            "Correlação de Spearman: associação entre a variável e a maior razão simulada.",
            "|Correlação|: força da associação sem sinal.",
            "Sentido: indica se valores maiores tendem a aumentar ou reduzir a razão.",
        ],
        "unit_note": "Correlação é adimensional e varia de -1 a +1.",
    },
    "sensitivity_results": {
        "number": 18,
        "caption": "Resumo dos resultados simulados por radionuclídeo e compartimento",
        "lead_text": (
            "A {table} consolida as faixas simuladas para cada radionuclídeo e compartimento. "
            "P95, razão contra Report Level e probabilidade empírica mostram a margem de segurança exploratória. "
            "Assim, a tabela localiza os resultados com maior proximidade da referência normativa."
        ),
        "column_notes": [
            "Radionuclídeo: radionuclídeo simulado.",
            "Compartimento: matriz ambiental simulada.",
            "Média: média dos valores simulados.",
            "Mínimo: menor valor simulado.",
            "Máximo: maior valor simulado.",
            "P95: percentil 95 dos valores simulados.",
            "Report Level: referência de notificação.",
            "P95 / Report Level: razão entre P95 e referência.",
            "Prob. > Report Level: fração de simulações acima da referência.",
        ],
        "unit_note": "Probabilidade e razão são adimensionais; os demais valores usam a unidade do compartimento.",
    },
    "minimums": {
        "number": 19,
        "caption": "Critérios mínimos para suficiência estatística",
        "lead_text": (
            "A {table} reúne os mínimos técnicos e os mínimos recomendados para testes estatísticos usuais. "
            "Os critérios mostram por que n calculado como número de radionuclídeos não substitui medições ambientais independentes. "
            "Assim, a tabela delimita quando a análise TAR pode avançar de descrição para inferência."
        ),
        "column_notes": [
            "Teste: procedimento estatístico considerado.",
            "Mínimo técnico: condição mínima para execução matemática do teste.",
            "Recomendado para relatório: condição prática para interpretação mais robusta.",
        ],
        "unit_note": "n representa contagem de observações ou pares, conforme o teste.",
    },
}


def tar_table_meta(key: str) -> dict[str, Any]:
    meta = dict(TAR_TABLES[key])
    number = meta["number"]
    table_label = f"Tabela {number}"
    meta["table_label"] = table_label
    meta["display_caption"] = f"{table_label} - {meta['caption']}"
    meta["lead_text"] = str(meta.get("lead_text") or "").format(table=table_label)
    meta["column_notes"] = list(meta.get("column_notes") or [])
    return meta
