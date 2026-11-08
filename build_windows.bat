@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Dong goi FE Vocab Trainer ===
echo Thu muc: %CD%

if not exist fe_vocab_trainer.py (
  echo THIEU file fe_vocab_trainer.py trong thu muc nay.
  pause
  exit /b 1
)
if not exist tuvung.txt (
  echo THIEU file tuvung.txt trong thu muc nay.
  pause
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo Khong tim thay Python. Cai Python va tick "Add Python to PATH" roi chay lai.
  pause
  exit /b 1
)
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo Cai PyInstaller that bai. Kiem tra ket noi mang.
  pause
  exit /b 1
)

set ICON_ARGS=
if exist icon.ico (
  set ICON_ARGS=--icon icon.ico --add-data "icon.ico;."
) else (
  echo [Luu y] Khong co icon.ico - se build khong co icon rieng.
)

python -m PyInstaller --noconfirm --clean --onefile --windowed --name FE_Vocab_Trainer %ICON_ARGS% --add-data "tuvung.txt;." fe_vocab_trainer.py
if errorlevel 1 (
  echo Dong goi that bai.
  pause
  exit /b 1
)
echo.
echo [1/2] Xong file chay: dist\FE_Vocab_Trainer.exe  (da gom san tu vung)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  if exist installer.iss if exist icon.ico (
    "%ISCC%" installer.iss
    echo [2/2] Xong bo cai dat: installer\FE_Vocab_Trainer_Setup.exe
  ) else (
    echo [2/2] Bo qua bo cai dat: can du installer.iss va icon.ico.
  )
) else (
  echo [2/2] Bo qua tao bo cai dat. Muon co Setup.exe: cai Inno Setup 6 ^(jrsoftware.org^) roi chay lai file nay.
)
pause
