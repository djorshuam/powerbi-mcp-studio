# powerbi-mcp-studio - configura o MCP do Power BI no app Claude Desktop (Windows)
# Uso: botao direito > "Executar com PowerShell"   (ou: powershell -ExecutionPolicy Bypass -File instalar-mcp-windows.ps1)
# O que faz: acha o npx, faz backup do claude_desktop_config.json, ACRESCENTA o servidor "powerbi-modeling"
# sem apagar os que ja existem, e valida o JSON. Nao instala nada alem disso.
$ErrorActionPreference = "Stop"
Write-Host "`n== powerbi-mcp-studio: configurando o MCP do Power BI ==`n"

# 1. Node.js / npx
$npx = (Get-Command npx.cmd -ErrorAction SilentlyContinue).Source
if (-not $npx -and (Test-Path "C:\Program Files\nodejs\npx.cmd")) { $npx = "C:\Program Files\nodejs\npx.cmd" }
if (-not $npx) {
  Write-Host "Node.js nao encontrado. Instale a versao LTS em https://nodejs.org e rode este script de novo." -ForegroundColor Yellow
  Start-Process "https://nodejs.org"; Read-Host "Enter para sair"; exit 1
}
Write-Host "npx: $npx"

# 2. Arquivo de configuracao (instalacao normal ou Microsoft Store)
$cands = @("$env:APPDATA\Claude\claude_desktop_config.json")
$cands += Get-ChildItem "$env:LOCALAPPDATA\Packages" -Directory -Filter "Claude_*" -ErrorAction SilentlyContinue |
          ForEach-Object { Join-Path $_.FullName "LocalCache\Roaming\Claude\claude_desktop_config.json" }
$cfg = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $cfg) {
  $dirs = $cands | Where-Object { Test-Path (Split-Path $_) }
  $cfg = if ($dirs) { $dirs | Select-Object -First 1 } else { $cands[0] }
  New-Item -ItemType Directory -Force -Path (Split-Path $cfg) | Out-Null
  Set-Content -Path $cfg -Value "{}" -Encoding UTF8
}
Write-Host "config: $cfg"

# 3. Backup + merge
$bak = "$cfg.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item $cfg $bak
$txt = Get-Content $cfg -Raw
if ([string]::IsNullOrWhiteSpace($txt)) { $txt = "{}" }
try { $j = $txt | ConvertFrom-Json } catch {
  Write-Host "O arquivo atual nao e um JSON valido. Nada foi alterado. Backup: $bak" -ForegroundColor Red
  Read-Host "Enter para sair"; exit 1
}
if (-not $j.PSObject.Properties["mcpServers"]) { $j | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) }
$srv = [pscustomobject]@{
  command = $npx
  args    = @("-y", "@microsoft/powerbi-modeling-mcp@latest", "--start", "--readwrite", "--require-confirmation")
}
if ($j.mcpServers.PSObject.Properties["powerbi-modeling"]) { $j.mcpServers."powerbi-modeling" = $srv }
else { $j.mcpServers | Add-Member -NotePropertyName "powerbi-modeling" -NotePropertyValue $srv }
$out = $j | ConvertTo-Json -Depth 20
$null = $out | ConvertFrom-Json   # valida antes de gravar
[System.IO.File]::WriteAllText($cfg, $out, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "`nPronto! Servidor 'powerbi-modeling' configurado. Backup do arquivo anterior: $bak" -ForegroundColor Green
Write-Host "Agora: FECHE o Claude Desktop pelo icone perto do relogio (Sair) e abra de novo."
Write-Host "Teste: abra um .pbix no Power BI Desktop e peca ao Claude 'identifique o arquivo Power BI aberto'."
Read-Host "`nEnter para sair"
