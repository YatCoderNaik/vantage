# Vantage 🚀: Telegram-First AI Execution Assistant

Vantage is a powerful, production-ready multi-agent Telegram Bot for Product Owners. Built on the **Google Agent Development Kit (ADK)** and powered by **Vertex AI** (`gemini-3.1-flash-lite-preview`, `gemini-1.5-flash`), Vantage seamlessly coordinates complex stakeholder requests, queries structured backlogs, optimizes schedules, and manages application databases natively using standard conversational language.

## 🌟 Key Features
- **Multi-Agent Orchestration**: A central `Orchestrator` agent dynamically routes queries to specialized sub-agents:
  - `CaptureAgent`: Structures raw stakeholder requests into ready-to-work User Stories/Epic drafts.
  - `QueryAgent`: Uses specialized queries against backend storage to summarize backlogs, sprints, and epic coverage.
  - `DecisionAgent`: Extracts implementation rationale and architecture decisions continuously, storing them via structured extraction.
  - `DatabaseExpert`: Leverages the **Oracle MCP Toolbox** to directly manage database state using dynamic SQL generation.
  - `ScheduleAgent`: Optimizes stakeholder meeting blocks.
- **Oracle Native Integration**: Deeply integrated with Oracle Cloud using native Thick-client mode & Wallets, securely resolving mTLS.
- **Zero-Trust Deployment Architecture**: Powered by Google Cloud Run. Entirely serverless Webhooks scaling. Secure bindings pull the Oracle Wallet Zip files, database keys, and Telegram credentials instantly from Google Cloud Secret Manager at startup.

## 🛠️ Architecture
- **Framework**: `python-telegram-bot` (v20+), `FastAPI` (for webhooks & health checks).
- **AI Core**: `google.adk`, `vertexai`, `google.genai`.
- **Database**: `oracledb` natively interacting with Oracle Autonomous Database.
- **Telemetry**: OpenTelemetry automatically instrumenting traces back to Google Cloud Trace.

## 🚀 Running Locally (Polling Mode)

1. **Clone & Install**:
   ```bash
   conda create --name google_adk python=3.10
   conda activate google_adk
   pip install -r requirements.txt
   ```
2. **Setup Secrets (`.env`)**:
   Populate the physical `.env` with:
   - `GOOGLE_CLOUD_PROJECT`
   - `TELEGRAM_BOT_TOKEN`
   - `DB_USER` / `DB_PASSWORD` / `DB_DSN` / `WALLET_PASSWORD`
   - `oracle-vantage-wallet-zip` must be in Secret Manager or unzipped locally.
3. **Execute**:
   ```powershell
   $env:PYTHONPATH="." 
   python vantage_bot/bot.py
   ```

## ☁️ Deploying to Google Cloud Run

Deploying horizontally scaling instances of Vantage relies on Google Cloud Build and Cloud Run natively. 

1. **Upload Secrets**: Make sure your telegram tokens and database variables are securely initialized inside Google Cloud Secret Manager. Upload your `wallet.zip` as a secret payload named `oracle-vantage-wallet-zip`.
2. **Deploy via Source**: Run the deployment batch file that handles auto-building and auto-binding of Secret Manager credentials:
   ```cmd
   deploy.bat
   ```
3. **Configure Webhook**:
   Once Cloud Run outputs your Service URL, update the Webhook URL in your Telegram Developer Portal (or supply it via Secret Manager as `WEBHOOK_URL` to let the code automatically register the endpoint on boot).
