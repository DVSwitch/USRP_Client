@echo off
setlocal

set "psCommand="(new-object -COM 'Shell.Application')^
.BrowseForFolder(0,'Seleccione a pasta onde se encontra o USRP Client',0,0).self.path""

for /f "usebackq delims=" %%I in (`powershell %psCommand%`) do set "folder=%%I"

setlocal enabledelayedexpansion

rem Download da library necessária:
SET "FILE_URL=https://files.pythonhosted.org/packages/94/3e/430d4e4e24e89b19c1df052644f69e03d64c1ae2e83f5a14bd365e0236de/PyAudio-0.2.11-cp27-cp27m-win_amd64.whl"
SET "SAVING_TO=!folder!"\PyAudio-0.2.11-cp37-cp37m-win_amd64.whl"
CALL :DOWNLOAD_FILE "%FILE_URL%" "%SAVING_TO%"
:DOWNLOAD_FILE
    rem Comando para fazer download:
    bitsadmin /transfer Download /download /priority normal %1 %2

cd !folder!
pip install PyAudio-0.2.11-cp37-cp37m-win_amd64.whl
pip install bs4
pip install Pillow
pip install requests
echo ""
echo "----------------------------------------------------------------------------------"
echo "Por favor, edite o ficheiro pyUC.ini com as suas credenciais (Indicativo, DMR ID)

Timeout /t 5
exit
