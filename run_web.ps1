Write-Host "Starting Product Data Extractor Web Server..." -ForegroundColor Cyan
Write-Host ""

# Token will be automatically loaded from token.md or .env by app.py
Write-Host "Token will be loaded automatically from token.md or .env file" -ForegroundColor Green
Write-Host ""

Write-Host "Starting Flask server on http://localhost:5000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python app.py

