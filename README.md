# TAR

Aplicação Flask independente para o módulo TAR e o ARTIGO BETA.

## Rotas

- `/` redireciona para `/tar/artigo-beta`
- `/tar`
- `/tar/artigo-beta`
- `/tar/report-preview`
- `/api/tar/summary`
- `/tar/export-report.docx`
- `/tar/export-report.pdf`
- `/healthz`

Parâmetros opcionais:

- `stat_n=60`
- `stat_seed=20260504`

Os parâmetros estatísticos permanecem aceitos por compatibilidade, mas o relatório principal não usa replicações aleatórias. A inferência atual usa somente as amostras reais do `TAR - Afluente` da planilha de atividade total; o `TAR - Efluente` é ignorado na análise.

## Execução local

```powershell
pip install -r requirements.txt
python app.py
```

Ou pelo PowerShell:

```powershell
.\iniciar_tar.ps1
```

Abra:

```text
http://127.0.0.1:5000/
```

## Render

O deploy usa `render.yaml`:

```text
python serve.py
```

A versão do Python é fixada em `.python-version` como `3.11.9` para usar wheels binários de `scipy==1.14.1`. Sem essa fixação, o Render pode usar Python 3.14 e tentar compilar SciPy a partir do código-fonte.

Variáveis esperadas:

- `TAR_WORKBOOK_PATH=./Cópia de TAR.xlsx`
- `TAR_ACTIVITY_WORKBOOK_PATH=./Atividade Total TAR c radionuclideos.xls`
- `TAR_TOTAL_ACTIVITY_WORKBOOK_PATH=./Dados Atividade TAR - Jayme (1).xlsx`
- `TAR_ARTICLE_PATH=./Artigo TAR1 correção.pdf`
