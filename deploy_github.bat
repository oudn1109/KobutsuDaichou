@echo off
cd /d "%~dp0"
set "GIT_EXE=C:\Users\hats1\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd\git.exe"
set "GH_EXE=C:\Users\hats1\AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin\gh.exe"
set "PATH=%PATH%;C:\Users\hats1\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd;C:\Users\hats1\AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin"

echo Checking GitHub authentication...
"%GH_EXE%" auth status
if errorlevel 1 (
    echo Starting GitHub Web Login...
    "%GH_EXE%" auth login --hostname github.com --git-protocol https --web
    "%GH_EXE%" auth setup-git
)

echo.
echo Pushing files to GitHub (oudn1109/KobutsuDaichou)...
"%GIT_EXE%" add .
"%GIT_EXE%" commit -m "Update app"
"%GIT_EXE%" push -u origin main --force

echo.
echo Done!
pause
