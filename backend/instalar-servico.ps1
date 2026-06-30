# Rode este script UMA VEZ num PowerShell aberto como Administrador
# (botao direito no icone do PowerShell -> "Executar como administrador").
#
# Registra o backend (FastAPI, que tambem serve o frontend) como tarefa
# agendada do Windows, iniciando sozinho no boot mesmo sem ninguem logado,
# e reiniciando sozinho se cair.

$ErrorActionPreference = "Stop"

$nomeTarefa = "PrevisaoEntregas-Backend"
$pastaBackend = "C:\previsao-entregas\backend"
$python = "$pastaBackend\venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Nao encontrei $python -- confirme se o venv ja foi criado (pip install -r requirements.txt)."
}

$acao = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" `
    -WorkingDirectory $pastaBackend

$gatilho = New-ScheduledTaskTrigger -AtStartup

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$config = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)  # 0 = sem limite de tempo de execucao

Unregister-ScheduledTask -TaskName $nomeTarefa -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $nomeTarefa `
    -Action $acao `
    -Trigger $gatilho `
    -Principal $principal `
    -Settings $config `
    -Description "Backend FastAPI do Controle de Entregas (Coco do Vale) -- tambem serve o frontend em http://<ip-do-servidor>:8000/"

$regraFirewall = "PrevisaoEntregas-Backend-8000"
if (-not (Get-NetFirewallRule -DisplayName $regraFirewall -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $regraFirewall -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow | Out-Null
    Write-Output "Regra de firewall criada: porta 8000 liberada para a rede."
} else {
    Write-Output "Regra de firewall ja existia."
}

Write-Output "Tarefa '$nomeTarefa' registrada. Iniciando agora para testar..."
Start-ScheduledTask -TaskName $nomeTarefa
Start-Sleep -Seconds 5
Get-ScheduledTaskInfo -TaskName $nomeTarefa | Format-List

Write-Output ""
Write-Output "Teste em outro navegador/maquina da rede: http://$($env:COMPUTERNAME):8000/"
Write-Output "(ou pelo IP da maquina: ipconfig | findstr IPv4)"
