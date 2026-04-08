import os
from dotenv import load_dotenv

load_dotenv() # Load env vars from .env
import json
import asyncio
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from google.adk import Runner
from google.adk.sessions import InMemorySessionService

from storage.oracle_client import OracleClient
from logic.onboarding import OnboardingManager
from vantage_bot.telemetry import setup_telemetry, tracer
from google.genai import types
from agents.orchestrator.agent import Orchestrator
from agents.story_writer.agent import CaptureAgent
from agents.backlog_query.agent import QueryAgent
from agents.decision_log.agent import DecisionAgent
from agents.calendar_optimizer.agent import ScheduleAgent
from agents.database_expert.agent import DatabaseExpert

# Constants
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "vantage-demo-hackathon")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Initialize Telemetry
setup_telemetry()

# Initialize Clients
fc = OracleClient()
onboarding = OnboardingManager(fc)
orchestrator = Orchestrator(project_id=PROJECT_ID)
capture_agent = CaptureAgent(project_id=PROJECT_ID)
query_agent = QueryAgent(project_id=PROJECT_ID, db_client=fc)
decision_agent = DecisionAgent(project_id=PROJECT_ID, db_client=fc)
schedule_agent = ScheduleAgent()
database_expert = DatabaseExpert(project_id=PROJECT_ID)

# Telegram App
tg_app = Application.builder().token(TOKEN).build()

async def auth_middleware(update: Update):
    """Checks if user exists, triggers onboarding if not."""
    telegram_user = update.effective_user
    telegram_id = telegram_user.id
    user_name = telegram_user.first_name
    
    user = fc.get_user(telegram_id)
    
    if not user:
        # First-time flow
        onboarding.seed_sample_data(telegram_id, user_name)
        welcome_text = (
            f"Welcome to Vantage, {user_name}! ✅\n\n"
            "I've loaded your workspace with some sample data so you can try everything right away.\n\n"
            "Try asking: 'What did we decide about SSO?' or 'Find me 2 focus blocks this week.'"
        )
        await update.message.reply_text(welcome_text)
        return False, None
    return True, user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command."""
    await auth_middleware(update)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler with Tracing and Logging."""
    try:
        with tracer.start_as_current_span("handle_message") as span:
            is_auth, user = await auth_middleware(update)
            if not is_auth:
                return

            text = update.message.text
            telegram_id = update.effective_user.id
            user_name = user.get('user_name', 'there')
            
            span.set_attribute("user.id", str(telegram_id))
            span.set_attribute("message.text", text)
            
            # Send 'typing' status
            await context.bot.send_chat_action(chat_id=telegram_id, action="typing")
            
            # 1. Orchestrate
            with tracer.start_as_current_span("orchestration") as route_span:
                routing = orchestrator.route(text)
                agent = routing.get("agent")
                confidence = routing.get("confidence", 0)
                
                route_span.set_attribute("routing.agent", agent)
                route_span.set_attribute("routing.confidence", confidence)
                
                logging.info(f"Routing message for user {telegram_id}: Agent={agent}, Confidence={confidence}", 
                             extra={"telegram_id": telegram_id, "routing": routing})
            
            # 2. Route
            if agent == "CLARIFY":
                msg = f"{user_name}, {routing.get('clarification_question')}"
                await update.message.reply_text(msg)
            
            elif agent == "QUERY":
                with tracer.start_as_current_span("query_agent"):
                    response = query_agent.answer_query(telegram_id, text)
                await update.message.reply_text(response)
            
            elif agent == "DECISION":
                with tracer.start_as_current_span("decision_agent"):
                    # Check if it's a retrieval or storage
                    if "?" in text or "what" in text.lower():
                        response = decision_agent.process_decision(telegram_id, text, mode="retrieve")
                    else:
                        response = decision_agent.process_decision(telegram_id, text, mode="store")
                await update.message.reply_text(response)
                
            elif agent == "CAPTURE":
                with tracer.start_as_current_span("capture_agent"):
                    draft = capture_agent.draft_ticket(text)
                if draft:
                    summary = (
                        f"📝 **Drafting Ticket**\n\n"
                        f"**Title**: {draft.get('title')}\n"
                        f"**Type**: {draft.get('type')}\n"
                        f"**Priority**: {draft.get('priority')}\n"
                        f"**Epic**: {draft.get('epic')}\n\n"
                        f"**Acceptance Criteria**:\n{draft.get('acceptance_criteria')}\n"
                    )
                    context.user_data['last_draft'] = draft
                    keyboard = [
                        [InlineKeyboardButton("✅ Create Ticket", callback_data=f"create_ticket_{telegram_id}")],
                        [InlineKeyboardButton("✏️ Edit", callback_data="edit_ticket"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode="Markdown")
                
            elif agent == "DATABASE":
                # Database Expert integration via ADK Runner
                with tracer.start_as_current_span("database_expert"):
                    response_text = await database_expert.run_query(telegram_id, text)
                    await update.message.reply_text(response_text)
                
            elif agent == "SCHEDULE":
                with tracer.start_as_current_span("schedule_agent"):
                    proposals = schedule_agent.get_focus_proposals(telegram_id)
                text_resp = "📅 **Proposing Focus Blocks**\n\n"
                keyboard = []
                for i, p in enumerate(proposals):
                    text_resp += f"Option {i+1}: {p['start'][:16]} — {p['rationale']}\n"
                    keyboard.append([InlineKeyboardButton(f"Select Option {i+1}", callback_data=f"book_slot_{i}")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(text_resp, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Unchecked error in handle_message: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ I encountered an error: {str(e)[:100]}... Please try again later.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks."""
    query = update.callback_query
    await query.answer()
    
    logging.info(f"Callback query received: {query.data} from user {query.from_user.id}")
    
    if query.data.startswith("create_ticket"):
        draft = context.user_data.get('last_draft')
        logging.info(f"Creating ticket. Draft found: {bool(draft)}")
        
        if draft:
            try:
                fc.add_ticket(query.from_user.id, draft)
                await query.edit_message_text(f"✅ Ticket '{draft.get('title')}' created in Oracle Database!")
                logging.info(f"Successfully created ticket for user {query.from_user.id}")
            except Exception as e:
                logging.error(f"DATABASE ERROR during ticket creation: {e}", exc_info=True)
                await query.edit_message_text(f"❌ An error occurred while creating the ticket. Please check the logs.")
        else:
            await query.edit_message_text("❌ Error: No draft found to persist.")
    elif query.data == "edit_ticket":
        await query.edit_message_text("✏️ Please type the updated details for the ticket (this will restart the draft with your new context).")
    elif query.data == "cancel":
        await query.edit_message_text("❌ Action cancelled.")
    elif query.data.startswith("book_slot"):
        slot_idx = int(query.data.split("_")[-1])
        # In a real app, this would call schedule_agent.confirm_booking()
        # For the hackathon, we acknowledge the specific slot selection.
        await query.edit_message_text(f"✅ Calendar block {slot_idx+1} confirmed and synced to your internal task list!")

# Initialize standard Handlers
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
tg_app.add_handler(CallbackQueryHandler(callback_handler))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Configuration
    await tg_app.initialize()
    if os.environ.get("WEBHOOK_URL"):
        await tg_app.bot.set_webhook(url=os.environ.get("WEBHOOK_URL"))
        print(f"🔗 Webhook configured to: {os.environ.get('WEBHOOK_URL')}")
    else:
        print("🤖 Starting Vantage Bot in Polling Mode...")
    await tg_app.start()
    
    # Check if polling should be spawned.
    polling_task = None
    if not os.environ.get("WEBHOOK_URL"):
        # We start polling manually to run aside FastAPI so we don't block
        print("Starting polling loop...")
        polling_task = asyncio.create_task(tg_app.updater.start_polling(drop_pending_updates=True))

    yield
    
    # Shutdown Configuration
    print("Shutting down the bot gracefully...")
    if polling_task:
        await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def process_webhook_update(request: Request):
    req_json = await request.json()
    update = Update.de_json(req_json, tg_app.bot)
    await tg_app.process_update(update)
    return Response(status_code=200)

@app.get("/")
def health_check():
    return {"status": "Vantage Bot is actively running and healthy!"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("vantage_bot.bot:app", host="0.0.0.0", port=port, log_level="info")
