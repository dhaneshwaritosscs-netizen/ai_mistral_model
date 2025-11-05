# PowerShell script to run the pipeline with API token set
param(
    [Parameter(Mandatory=$true)]
    [string]$Url,
    
    [Parameter(Mandatory=$false)]
    [string[]]$Fields
)

# Set the Mistral API token
$env:HF_TOKEN = "YXzyDmU7DWCCn2ehudOJS4V6QRef1mf4"

Write-Host "API Token set. Processing URL: $Url" -ForegroundColor Green

# Build command arguments
$args = @($Url)
if ($Fields) {
    $args += $Fields
}

# Run the pipeline
python .\pipeline.py $args

# Check if token is still needed
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nNote: If you see 'HF_TOKEN not set' error, make sure the token is correct." -ForegroundColor Yellow
}

