# Estatística do Projeto TAR

## Premissa de entrada

Os valores de concentração da água do Tanque de Água de Recarregamento (TAR) devem ser tratados como dados medidos quando forem obtidos por espectrometria gama em amostras reais da água do tanque.

Esses valores medidos alimentam a simulação de transporte para os compartimentos ambientais avaliados: água do mar, peixe, invertebrado e sedimento. Assim, cada conjunto de medições do TAR pode gerar uma nova simulação. Quando houver n medições independentes ou n campanhas com resultados válidos, o projeto poderá produzir n simulações e comparar a distribuição dos resultados simulados com os limites de referência da norma, Report Level e LLD, quando aplicável.

Na implementação atual, a base inferencial vem da planilha `Atividade Total TAR c radionuclideos.xls`, usando somente o grupo `TAR - Afluente`. O grupo `TAR - Efluente` não entra nos cálculos, tabelas ou testes. Valores marcados como `< MDA>` são tratados como censurados: entram nas contagens, mas não são convertidos para zero nem para MDA/2.

## O que pode ser feito com a planilha atual

Com a base atual, já é tecnicamente adequado:

- calcular as concentrações simuladas por radionuclídeo e por compartimento ambiental;
- comparar cada resultado com Report Level e LLD disponíveis;
- calcular a razão resultado/referência;
- identificar valores abaixo, acima ou sem referência;
- comparar os cenários A1 e A1 e A2;
- apresentar margem de segurança em relação aos limites normativos disponíveis;
- aplicar inferência aos resultados calculados por amostra real do `TAR - Afluente`, quando houver n suficiente por radionuclídeo e compartimento.

Essa etapa responde se os resultados calculados a partir das amostras reais ultrapassam os limites cadastrados e qual é a incerteza da frequência observada de ultrapassagem.

## O que muda quando houver n medições do TAR

Quando forem cadastradas medições repetidas por espectrometria gama, a unidade amostral passa a ser a medição da água do TAR ou a campanha de medição, conforme a forma de coleta.

Cada linha de entrada deve conter, no mínimo:

- identificador da amostra ou campanha;
- data da coleta;
- cenário de cálculo;
- radionuclídeo;
- concentração medida na água do TAR;
- unidade;
- incerteza analítica, quando disponível;
- LLD/MDA ou indicação de resultado abaixo do limite de detecção;
- observação sobre valor censurado, rejeitado ou revisado.

Com esses dados, o projeto poderá gerar uma simulação para cada medição ou campanha. O resultado principal deixará de ser um único valor calculado e passará a ser uma distribuição de concentrações simuladas por radionuclídeo e compartimento.

## Cenário hipotético

O módulo ainda mantém o cenário hipotético como recurso técnico separado, mas ele não é a base estatística do relatório principal. A análise principal deve usar as amostras reais do `TAR - Afluente`.

Cada medição sintética alimenta uma nova simulação. O painel passa a mostrar:

- n medições sintéticas por radionuclídeo;
- resumo das concentrações medidas da água do TAR;
- percentil 95 das concentrações simuladas por compartimento ambiental;
- razão P95/Report Level;
- teste estatístico utilizado;
- texto explicando a escolha do teste.

A geração hipotética é pseudoaleatória e reprodutível por `seed`, quando esse cenário for selecionado explicitamente.

## Estatística recomendada para o TAR

A comparação principal deve continuar sendo contra os limites da norma. O ponto estatístico relevante não é apenas testar diferença entre grupos, mas estimar a chance ou a margem de ultrapassagem do limite.

Análises recomendadas:

- estatística descritiva das concentrações medidas no TAR: n, média, mediana, desvio-padrão, mínimo, máximo e percentis;
- propagação das medições reais do `TAR - Afluente` pela fórmula da planilha, preservando a ligação entre amostra de entrada e resultado calculado;
- razão simulada/limite para cada radionuclídeo e compartimento;
- percentil 95 ou 97,5 das simulações como estimativa conservadora;
- intervalo de confiança unilateral superior para a média ou para o percentil, quando houver n suficiente;
- probabilidade empírica de ultrapassagem: número de simulações acima do limite dividido por n;
- limite superior binomial de 95% para a probabilidade de ultrapassagem quando nenhuma simulação exceder o limite;
- análise de sensibilidade para identificar quais radionuclídeos mais contribuem para a proximidade com o limite.

Testes como Shapiro-Wilk, teste t, Wilcoxon, ANOVA, Kruskal-Wallis e Friedman só entram se houver uma pergunta comparativa clara, por exemplo comparar cenários, campanhas, períodos, usinas ou métodos de medição. Para a pergunta principal do TAR, a leitura mais importante é a comparação da distribuição simulada com os limites normativos.

Na análise real implementada, a comparação inferencial usa o logaritmo da razão entre valor calculado por amostra e Report Level. O Shapiro-Wilk verifica a normalidade dessas razões. Quando a normalidade é atendida, aplica-se teste t unilateral de uma amostra. Quando a normalidade não é atendida, aplica-se Wilcoxon unilateral de uma amostra. A hipótese alternativa é que os resultados calculados permaneçam abaixo do Report Level, tratado como referência fixa.

## Comparação com ERICA Tool

Os valores do ERICA Tool podem ser usados como estimativa visual enquanto as saídas reais não forem fornecidas. A comparação pareada usa os pares radionuclídeo-compartimento calculados pela fórmula e estimados pelo ERICA. Essa comparação é exploratória e não substitui validação regulatória.

Report Level e LLD permanecem referências fixas. Eles não são amostras, não são randomizados e não entram como observações nos testes.

## Mínimos práticos de amostra

Os mínimos abaixo orientam a coleta futura:

| Objetivo | Mínimo técnico | Recomendado |
|---|---:|---:|
| Estatística descritiva simples | n >= 3 | n >= 10 |
| Verificar normalidade por Shapiro-Wilk | n >= 3 | n >= 8 a 10 |
| Estimar percentil 95 de forma estável | n >= 20 | n >= 50 |
| Estimar probabilidade de ultrapassagem | n >= 20 | n >= 50 a 100 |
| Afirmar, com 95% de confiança, que a probabilidade de ultrapassagem é menor que 5% quando não há excedências | n >= 59 simulações sem excedência | n >= 60 ou mais |
| Afirmar, com 95% de confiança, que a probabilidade de ultrapassagem é menor que 1% quando não há excedências | n >= 299 simulações sem excedência | n >= 300 ou mais |
| Teste t pareado ou Wilcoxon entre dois cenários | n >= 2 pares | n >= 10 pares |
| Teste t independente ou Mann-Whitney entre dois grupos | n >= 2 por grupo para t; n >= 1 por grupo para Mann-Whitney | n >= 10 por grupo |
| ANOVA ou Kruskal-Wallis entre mais de dois grupos | n >= 2 por grupo para ANOVA | n >= 5 a 10 por grupo |

## Conclusão operacional

Com os arquivos atuais, o módulo TAR usa o `TAR - Afluente` como base amostral real, transforma cada amostra válida em resultado por compartimento e compara a distribuição calculada com o Report Level fixo. A leitura principal combina estatística descritiva, frequência de ultrapassagem, IC95% binomial e p-value quando o n permite teste sobre log(valor/Report Level).
