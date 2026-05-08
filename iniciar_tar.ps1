param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5000,
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if ($Install) {
    Write-Host "Instalando dependencias de requirements.txt..."
    python -m pip install -r requirements.txt
}

$env:HOST = $HostName
$env:PORT = [string]$Port
$env:TAR_WORKBOOK_PATH = Join-Path $ProjectRoot "Cópia de TAR.xlsx"
$env:TAR_ACTIVITY_WORKBOOK_PATH = Join-Path $ProjectRoot "Atividade Total TAR c radionuclideos.xls"
$env:TAR_ARTICLE_PATH = Join-Path $ProjectRoot "Artigo TAR1 correção.pdf"

Write-Host "Iniciando TAR em http://$HostName`:$Port/"
Write-Host "Use Ctrl+C para encerrar."
python app.py
