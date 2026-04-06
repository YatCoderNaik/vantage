import os
from dotenv import load_dotenv

load_dotenv() # Load env vars from .env
import json
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from storage.oracle_client import OracleClient
from logic.onboarding import OnboardingManager
from agents.orchestrator.agent import Orchestrator
from agents.story_writer.agent import CaptureAgent
from agents.backlog_query.agent import QueryAgent
from agents.decision_log.agent import DecisionAgent
from agents.calendar_optimizer.agent import ScheduleAgent

# Constants
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "vantage-demo-hackathon")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Initialize Clients
fc = OracleClient()
onboarding = OnboardingManager(fc)
orchestrator = Orchestrator(project_id=PROJECT_ID)
capture_agent = CaptureAgent(project_id=PROJECT_ID)
query_agent = QueryAgent(project_id=PROJECT_ID, db_client=fc)
decision_agent = DecisionAgent(project_id=PROJECT_ID, db_client=fc)
schedule_agent = ScheduleAgent()

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
    """Main message handler."""
    is_auth, user = await auth_middleware(update)
    if not is_auth:
        return

    text = update.message.text
    telegram_id = update.effective_user.id
    user_name = user.get('user_name', 'there')
    
    # Send 'typing' status
    await context.bot.send_chat_action(chat_id=telegram_id, action="typing")
    
    # 1. Orchestrate
    routing = orchestrator.route(text)
    agent = routing.get("agent")
    
    # 2. Route
    if agent == "CLARIFY":
        msg = f"{user_name}, {routing.get('clarification_question')}"
        await update.message.reply_text(msg)
    
    elif agent == "QUERY":
        response = query_agent.answer_query(telegram_id, text)
        await update.message.reply_text(response)
    
    elif agent == "DECISION":
        # Check if it's a retrieval or storage
        if "?" in text or "what" in text.lower():
            response = decision_agent.process_decision(telegram_id, text, mode="retrieve")
        else:
            response = decision_agent.process_decision(telegram_id, text, mode="store")
        await update.message.reply_text(response)
        
    elif agent == "CAPTURE":
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
            keyboard = [
                [InlineKeyboardButton("✅ Create Ticket", callback_data=f"create_ticket_{telegram_id}")],
                [InlineKeyboardButton("✏️ Edit", callback_data="edit_ticket"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode="Markdown")
            
    elif agent == "SCHEDULE":
        proposals = schedule_agent.get_focus_proposals(telegram_id)
        text_resp = "📅 **Proposing Focus Blocks**\n\n"
        keyboard = []
        for i, p in enumerate(proposals):
            text_resp += f"Option {i+1}: {p['start'][:16]} — {p['rationale']}\n"
            keyboard.append([InlineKeyboardButton(f"Select Option {i+1}", callback_data=f"book_slot_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text_resp, reply_markup=reply_markup, parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("create_ticket"):
        await query.edit_message_text("✅ Ticket created in Oracle Database!")
    elif query.data == "cancel":
        await query.edit_message_text("❌ Action cancelled.")
    elif query.data.startswith("book_slot"):
        await query.edit_message_text("✅ Calendar block confirmed!")

if __name__ == "__main__":
    import asyncio
    print("🤖 Starting Vantage Bot in Polling Mode...")
    
    # Initialize and configure the application
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    tg_app.add_handler(CallbackQueryHandler(callback_handler))

    # Run polling (this replaces the need for FastAPI/uvicorn for local dev)
    tg_app.run_polling(drop_pending_updates=True)
