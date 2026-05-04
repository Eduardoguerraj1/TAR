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

## Execução local

```powershell
pip install -r requirements.txt
python app.py
```

Abra:

```text
http://127.0.0.1:5000/
```

## Render

O deploy usa `render.yaml`:

```text
waitress-serve --host=0.0.0.0 --port=$PORT wsgi:application
```

Variáveis esperadas:

- `TAR_WORKBOOK_PATH=./Cópia de TAR.xlsx`
- `TAR_ARTICLE_PATH=./Artigo TAR1 correção.pdf`
