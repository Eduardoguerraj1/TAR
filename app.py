from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, redirect, request

from tar_project import (
    TarWorkbookError,
    build_tar_docx_payload,
    build_tar_pdf_payload,
    build_tar_summary,
    render_tar_article_beta_html,
    render_tar_dashboard_html,
    render_tar_report_html,
)


BASE_DIR = Path(__file__).resolve().parent


def resolve_config_path(name: str, default: Path) -> Path:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return (BASE_DIR / path).resolve()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


app = Flask(__name__)

TAR_WORKBOOK_PATH = resolve_config_path("TAR_WORKBOOK_PATH", BASE_DIR / "Cópia de TAR.xlsx")
TAR_ACTIVITY_WORKBOOK_PATH = resolve_config_path(
    "TAR_ACTIVITY_WORKBOOK_PATH",
    BASE_DIR / "Atividade Total TAR c radionuclideos.xls",
)
TAR_ARTICLE_PATH = resolve_config_path("TAR_ARTICLE_PATH", BASE_DIR / "Artigo TAR1 correção.pdf")


def current_tar_summary() -> dict[str, Any]:
    return build_tar_summary(
        TAR_WORKBOOK_PATH,
        request.args.get("scenario", "a1"),
        activity_workbook_path=TAR_ACTIVITY_WORKBOOK_PATH,
        hypothetical_n=request.args.get("n", 60),
        hypothetical_seed=request.args.get("seed", 20260504),
        sensitivity_n=request.args.get("sensitivity_n", 10000),
        sensitivity_seed=request.args.get("sensitivity_seed", 20260504),
        stat_n=request.args.get("stat_n", 60),
        stat_seed=request.args.get("stat_seed", 20260504),
    )


def tar_error_response(exc: Exception, *, as_json: bool = False):
    message = str(exc)
    if as_json:
        return jsonify(
            {
                "ok": False,
                "error": message,
                "workbook_path": str(TAR_WORKBOOK_PATH),
                "activity_workbook_path": str(TAR_ACTIVITY_WORKBOOK_PATH),
            }
        ), 500
    return Response(message, status=500, content_type="text/plain; charset=utf-8")


@app.get("/")
def index():
    return redirect("/tar/artigo-beta", code=302)


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "ok": True,
            "service": "tar-beta",
            "workbook_path": str(TAR_WORKBOOK_PATH),
            "activity_workbook_path": str(TAR_ACTIVITY_WORKBOOK_PATH),
            "article_path": str(TAR_ARTICLE_PATH),
        }
    )


@app.get("/tar")
def tar_dashboard():
    try:
        summary = current_tar_summary()
    except TarWorkbookError as exc:
        return tar_error_response(exc)
    return Response(render_tar_dashboard_html(summary), content_type="text/html; charset=utf-8")


@app.route("/api/tar/summary", methods=["GET", "OPTIONS"])
def api_tar_summary():
    if request.method == "OPTIONS":
        return Response(status=204)
    try:
        summary = current_tar_summary()
    except TarWorkbookError as exc:
        return tar_error_response(exc, as_json=True)
    return jsonify(json_ready(summary))


@app.get("/tar/report-preview")
def tar_report_preview():
    try:
        summary = current_tar_summary()
    except TarWorkbookError as exc:
        return tar_error_response(exc)
    return Response(render_tar_report_html(summary), content_type="text/html; charset=utf-8")


@app.get("/tar/artigo-beta")
def tar_article_beta():
    try:
        summary = current_tar_summary()
        html = render_tar_article_beta_html(summary, TAR_ARTICLE_PATH)
    except Exception as exc:
        return tar_error_response(exc)
    return Response(html, content_type="text/html; charset=utf-8")


@app.get("/tar/export-report.docx")
def tar_export_report_docx():
    try:
        summary = current_tar_summary()
        payload, filename, content_type = build_tar_docx_payload(summary)
    except Exception as exc:
        return tar_error_response(exc)
    return Response(
        payload,
        content_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/tar/export-report.pdf")
def tar_export_report_pdf():
    try:
        summary = current_tar_summary()
        payload, filename, content_type = build_tar_pdf_payload(summary)
    except Exception as exc:
        return tar_error_response(exc)
    return Response(
        payload,
        content_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    host = (os.getenv("HOST") or "127.0.0.1").strip()
    port = int(os.getenv("PORT") or "5000")
    app.run(debug=False, host=host, port=port)
