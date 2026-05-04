# Projeto TAR

Este pacote concentra o módulo TAR separado do fluxo principal da UAS.

## Responsabilidades do pacote

- carregar a planilha `Cópia de TAR.xlsx` ou o caminho definido por `TAR_WORKBOOK_PATH`;
- tratar `A1` e `A1 e A2` como cenários de cálculo;
- consolidar concentrações por radionuclídeo e compartimento ambiental;
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

O cenário `hipotetico` aceita os parâmetros opcionais `n` e `seed`. Todas as rotas TAR também aceitam `sensitivity_n` e `sensitivity_seed` para a análise de sensibilidade Monte Carlo.

Exemplo:

```text
/tar?scenario=hipotetico&n=60&seed=20260504&sensitivity_n=10000&sensitivity_seed=20260504
```

Esse cenário não altera a planilha Excel. Ele usa os valores atuais como base, gera medições sintéticas da água do TAR por espectrometria gama e propaga essas entradas para novas simulações.

A análise de sensibilidade usa intervalos sintéticos demonstrativos e multiplicadores simples sobre os resultados atuais. Ela serve para triagem exploratória das variáveis mais influentes e não substitui constantes de literatura nem conclusão regulatória.

## Documentação estatística

A premissa estatística do TAR está em `tar_project/docs/ESTATISTICA.md`.

O ponto principal é que os valores da água do TAR podem ser medições reais obtidas por espectrometria gama. Quando houver n medições independentes, cada medição poderá alimentar uma simulação, permitindo comparar a distribuição dos resultados simulados com os limites normativos.

Enquanto houver apenas uma planilha consolidada por cenário, a análise permanece descritiva e determinística.
