@echo off
REM Abre o painel em modo quiosque: tela cheia, sem barra de endereco,
REM sem abas, sem nada do navegador. Ideal para deixar fixo numa TV/monitor.
REM Pressione Alt+F4 para fechar.
REM
REM Se este script rodar na MESMA maquina que serve o backend, deixe como
REM esta. Se for rodar numa TV/outro computador da rede, troque a URL
REM abaixo pelo endereco do servidor (ex: http://NB-CTRL-02:8000/).

set URL=http://localhost:8000/

set EDGE1=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
set EDGE2=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe
set CHROME1=%ProgramFiles%\Google\Chrome\Application\chrome.exe
set CHROME2=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe

if exist "%EDGE1%" (
    start "" "%EDGE1%" --kiosk "%URL%" --edge-kiosk-type=fullscreen --no-first-run
    goto :fim
)
if exist "%EDGE2%" (
    start "" "%EDGE2%" --kiosk "%URL%" --edge-kiosk-type=fullscreen --no-first-run
    goto :fim
)
if exist "%CHROME1%" (
    start "" "%CHROME1%" --kiosk "%URL%"
    goto :fim
)
if exist "%CHROME2%" (
    start "" "%CHROME2%" --kiosk "%URL%"
    goto :fim
)

echo Nao encontrei o Edge nem o Chrome instalados. Abrindo no navegador padrao (sem modo quiosque)...
start "" "%URL%"

:fim
