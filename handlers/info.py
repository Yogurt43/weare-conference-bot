# handlers/info.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

import db
import utils
from strings import t
from config import QA_RATE_LIMIT, GROUP_CHAT_ID

# In-memory state for "expecting message" (keyed by chat_id)
_awaiting_qa: set[int] = set()
_awaiting_msg: set[int] = set()


async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    participant = db.get_participant(update.effective_chat.id)
    lang = utils.get_lang(participant)
    text = db.get_setting('schedule_text')
    await query.edit_message_text(text or t(lang, 'no_schedule'), parse_mode=ParseMode.MARKDOWN)


async def handle_venue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    participant = db.get_participant(update.effective_chat.id)
    lang = utils.get_lang(participant)
    text = db.get_setting('venue_text')
    await query.edit_message_text(text or t(lang, 'no_venue'), parse_mode=ParseMode.MARKDOWN)


async def handle_qa_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    if db.is_paused('qa'):
        await query.edit_message_text(t(lang, 'qa_paused'))
        return

    count = db.count_questions_by_participant(participant['id'])
    if count >= QA_RATE_LIMIT:
        await query.edit_message_text(t(lang, 'qa_rate_limited', limit=QA_RATE_LIMIT))
        return

    _awaiting_qa.add(chat_id)
    await query.edit_message_text(t(lang, 'qa_prompt'))


async def handle_coordinator_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    if db.is_paused('messages'):
        await query.edit_message_text(t(lang, 'messages_paused'))
        return

    _awaiting_msg.add(chat_id)
    await query.edit_message_text(t(lang, 'coordinator_prompt'))


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches free-text from users who are in QA or coordinator message flow."""
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)
    text = update.message.text.strip()

    # Resolve the organiser channel once — used by both Q&A and messages
    def _org_channel():
        stored = db.get_setting('coord_channel_id')
        return int(stored) if stored else GROUP_CHAT_ID

    if chat_id in _awaiting_qa:
        _awaiting_qa.discard(chat_id)
        db.save_question(participant['id'], text)
        await update.message.reply_text(t(lang, 'qa_submitted'))
        target = _org_channel()
        if target:
            name = participant.get('full_name', 'Unknown')
            await context.bot.send_message(
                target,
                f"❓ *Question from {name}*\n\n{text}",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    if chat_id in _awaiting_msg:
        _awaiting_msg.discard(chat_id)
        db.save_message(participant['id'], text)
        await update.message.reply_text(t(lang, 'coordinator_submitted'))
        target = _org_channel()
        if target:
            name = participant.get('full_name', 'Unknown')
            await context.bot.send_message(
                target,
                f"📨 *Message from {name}*\n\n{text}",
                parse_mode=ParseMode.MARKDOWN,
            )
        return


def get_info_handlers() -> list:
    return [
        CallbackQueryHandler(handle_schedule,          pattern='^menu_schedule$'),
        CallbackQueryHandler(handle_venue,             pattern='^menu_venue$'),
        CallbackQueryHandler(handle_qa_start,          pattern='^menu_qa$'),
        CallbackQueryHandler(handle_coordinator_start, pattern='^menu_coordinator$'),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input),
    ]
