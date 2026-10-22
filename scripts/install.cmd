@echo off
rem Instala o sen com dois cliques: chama o install.ps1 desta pasta.
rem Sai da pasta antes, para a janela nao segurar a pasta que o instalador apaga no fim.
rem Tudo numa linha, terminando em (goto): o instalador apaga este arquivo, e o cmd
rem nao pode voltar a le-lo depois.
cd /d "%TEMP%" & powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" & pause & (goto) 2>nul
