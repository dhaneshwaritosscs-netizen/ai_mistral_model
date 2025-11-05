@echo off
REM Batch script to run the pipeline with API token set

if "%~1"=="" (
    echo Usage: run_pipeline.bat ^<URL^> [field1] [field2] ...
    echo Example: run_pipeline.bat "https://www.flipkart.com/product-url" price
    echo Example: run_pipeline.bat "https://www.flipkart.com/product-url" price rating review
    echo Available fields: price, rating, review, ratings_count, reviews_count, product_name, discount, availability
    exit /b 1
)

echo Setting API Token...
set HF_TOKEN=YXzyDmU7DWCCn2ehudOJS4V6QRef1mf4
echo Processing URL: %1
if not "%~2"=="" (
    echo Extracting fields: %*
)
echo.

python pipeline.py %*

if errorlevel 1 (
    echo.
    echo Note: If you see 'HF_TOKEN not set' error, check the token in this script.
)

