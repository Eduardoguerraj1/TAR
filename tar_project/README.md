# Projeto TAR

Este pacote concentra o módulo TAR separado do fluxo principal da UAS.

## Responsabilidades do pacote

- carregar a planilha `Cópia de TAR.xlsx` ou o caminho definido por `TAR_WORKBOOK_PATH`;
- carregar a planilha empírica `Atividade Total TAR c radionuclideos.xls` ou o caminho definido por `TAR_ACTIVITY_WORKBOOK_PATH`;
- tratar `A1` e `A1 e A2` como cenários de cálculo;
- consolidar concentrações por radionuclídeo e compartimento ambiental;
- complementar a estatística com dados reais de atividade total TAR usando somente `TAR - Afluente`;
- comparar resultados com Report Level e LLD disponíveis;
- gerar dashboard, preview HTML e exportações DOCX/PDF do TAR;
- manter a avaliação estatística do TAR separada da lógica estatística da UAS.

## Rotas Flask registradas em app.py

- `/tar`
- `/api/tar/summary?scenario=a1|a1_a2|hipotetico`
- `/tar/report-preview?scenario=a1|a1_a2|hipotetico`
- `/tar/artigo-beta?scenario=a1|a1_a2|hipotetico`
- `/tar/export-report.docx?scenario=a1|a1_a2|hipotetico`
- `/tar/export-report.pdf?scenario=a1|a1_a2|hipotetico`

O arquivo `tar_app.py` é a entrada dedicada para publicar o TAR como serviço Render separado. Nesse modo, a raiz do serviço (`/`) redireciona para `/tar/artigo-beta`, mantendo o link do UAS independente.

O cenário `hipotetico` aceita os parâmetros opcionais `n` e `seed`. As rotas TAR mantêm `sensitivity_n` e `sensitivity_seed` por compatibilidade, mas o relatório principal não usa análise aleatória de sensibilidade.

Exemplo:

```text
/tar?scenario=hipotetico&n=60&seed=20260504&sensitivity_n=10000&sensitivity_seed=20260504
```

Esse cenário não altera a planilha Excel. Ele usa os valores atuais como base, gera medições sintéticas da água do TAR por espectrometria gama e propaga essas entradas para novas simulações.

O ARTIGO BETA separa dados calculados por fórmulas, dados estimados pelo ERICA Tool e normas de comparação. A inferência principal usa as amostras reais do `TAR - Afluente`; Report Level e LLD permanecem referências fixas.

## Documentação estatística

A premissa estatística do TAR está em `tar_project/docs/ESTATISTICA.md`.

O ponto principal é que os valores da água do TAR são tratados como medições reais obtidas por espectrometria gama. Cada amostra válida do `TAR - Afluente` alimenta o cálculo por fórmula, permitindo comparar a distribuição dos resultados calculados com o Report Level fixo.
