@echo off
setlocal

:: Ensure GOOGLE_CLOUD_PROJECT is set
if "%GOOGLE_CLOUD_PROJECT%"=="" (
    echo "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set."
    exit /b 1
)

set SERVICE_NAME=vantage-bot
set REGION=us-central1
set IMAGE_URL=gcr.io/%GOOGLE_CLOUD_PROJECT%/%SERVICE_NAME%

echo "Building Docker image..."
gcloud builds submit --tag %IMAGE_URL%

echo "Deploying to Cloud Run..."
gcloud run deploy %SERVICE_NAME% ^
  --image %IMAGE_URL% ^
  --region %REGION% ^
  --platform managed ^
  --allow-unauthenticated ^
  --set-env-vars=GOOGLE_CLOUD_PROJECT=%GOOGLE_CLOUD_PROJECT%,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=1 ^
  --update-secrets=TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,DB_USER=DB_USER:latest,DB_PASSWORD=DB_PASSWORD:latest,WALLET_PASSWORD=WALLET_PASSWORD:latest

echo "Deployment complete!"
echo "NOTE: Make sure to set the WEBHOOK_URL in Google Secret Manager or directly via Cloud Run so the bot uses Webhooks instead of Polling."
