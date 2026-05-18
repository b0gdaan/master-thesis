@echo off
REM upload_to_server.bat
REM Uploads thesis website files to VPS and runs deploy.sh
REM Requirements: OpenSSH (built into Windows 10/11) or PuTTY's pscp in PATH

setlocal

set SERVER=root@72.56.38.144
set REMOTE_TMP=/tmp/thesis_upload
set LOCAL_DIR=%~dp0

echo === Thesis Website Deployment ===
echo Server : %SERVER%
echo Source : %LOCAL_DIR%
echo.

REM Create remote temp directory
echo [1/5] Creating remote temp directory...
ssh %SERVER% "mkdir -p %REMOTE_TMP%/figures"

REM Upload main HTML
echo [2/5] Uploading index.html...
scp "%LOCAL_DIR%index.html" %SERVER%:%REMOTE_TMP%/index.html

REM Upload nginx config
echo [3/5] Uploading nginx config...
scp "%LOCAL_DIR%nginx_thesis.conf" %SERVER%:%REMOTE_TMP%/nginx_thesis.conf

REM Upload deploy script
echo [4/5] Uploading deploy script...
scp "%LOCAL_DIR%deploy.sh" %SERVER%:%REMOTE_TMP%/deploy.sh

REM Upload figures (if directory exists locally)
if exist "%LOCAL_DIR%figures\" (
    echo [5/5] Uploading figures...
    scp -r "%LOCAL_DIR%figures\*" %SERVER%:%REMOTE_TMP%/figures/
) else (
    echo [5/5] No local figures\ directory found. Skipping figures upload.
    echo       To upload figures later, run:
    echo       scp -r "D:\master rad\outputs\figures\*" root@72.56.38.144:/var/www/thesis/figures/
)

REM Run deploy script on server
echo.
echo === Running deploy.sh on server ===
ssh %SERVER% "bash %REMOTE_TMP%/deploy.sh"

echo.
echo === Upload complete ===
echo Visit: http://72.56.38.144:8080
pause
