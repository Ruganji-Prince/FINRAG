$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $project
$pythonExe = Join-Path $project '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run the README installation steps first.' }
Start-Process -FilePath $pythonExe -ArgumentList '-m uvicorn backend.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $project 'data\backend.log') -RedirectStandardError (Join-Path $project 'data\backend-error.log')
Start-Process -FilePath $pythonExe -ArgumentList '-m streamlit run app/streamlit_app.py --server.headless true --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false' -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $project 'data\frontend.log') -RedirectStandardError (Join-Path $project 'data\frontend-error.log')
Write-Host 'FinRAG: http://127.0.0.1:8501 | API: http://127.0.0.1:8000/docs'
