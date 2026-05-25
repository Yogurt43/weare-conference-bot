# handlers/housing.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

import db
import utils
from strings import t

# Button texts for both languages — used to build the MessageHandler filter
_HOUSING_TEXTS = [t('en', 'btn_housing'), t('uk', 'btn_housing')]


async def handle_housing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    # Only approved participants can use the persistent menu
    if not participant or participant.get('status') != 'approved':
        return

    if db.is_paused('housing'):
        await update.message.reply_text(t(lang, 'housing_paused'))
        return

    # Already has a reservation — show it, no changes allowed
    reservation = db.get_reservation(participant['id'])
    if reservation:
        house = reservation['houses']
        await update.message.reply_text(
            t(lang, 'current_reservation', name=house['name']),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Ask if they need housing; Yes leads to the house list
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, 'btn_housing_yes'), callback_data='menu_housing_yes')],
        [InlineKeyboardButton(t(lang, 'btn_housing_no'),  callback_data='menu_housing_no')],
    ])
    await update.message.reply_text(t(lang, 'housing_prompt'), reply_markup=keyboard)


async def _show_house_list(query, participant: dict, lang: str):
    """Render the available-houses list into the current message."""
    gender = participant.get('gender', 'M')
    houses = db.get_houses_for_gender(gender)
    if not houses:
        await query.edit_message_text(t(lang, 'no_houses_available'))
        return
    buttons = []
    for house in houses:
        taken = db.get_house_occupancy(house['id'])
        if taken >= house['capacity']:
            continue
        label = utils.format_house_button(house, taken, lang)
        buttons.append([InlineKeyboardButton(label, callback_data=f"house_{house['id']}")])
    if not buttons:
        await query.edit_message_text(t(lang, 'no_houses_available'))
        return
    await query.edit_message_text(
        t(lang, 'housing_list_header'),
        reply_markup=InlineKeyboardMarkup(buttons),
    )



async def handle_housing_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = utils.get_lang(db.get_participant(update.effective_chat.id))
    await query.edit_message_text(t(lang, 'no_housing_needed'))


async def handle_housing_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    participant = db.get_participant(update.effective_chat.id)
    lang = utils.get_lang(participant)
    await _show_house_list(query, participant, lang)


async def handle_house_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    if not participant:
        await query.edit_message_text(t('en', 'error_generic'))
        return
    lang = utils.get_lang(participant)

    house_id = query.data.replace('house_', '')
    house = db.get_house_by_id(house_id)
    if not house:
        await query.edit_message_text(t(lang, 'error_generic'))
        return

    taken = db.get_house_occupancy(house_id)
    if taken >= house['capacity']:
        await query.edit_message_text(t(lang, 'house_full_msg'))
        return

    context.user_data['pending_house_id'] = house_id

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, 'btn_confirm_yes'), callback_data=f'houseconfirm_{house_id}')],
    ])
    await query.edit_message_text(
        t(lang, 'house_confirm', name=house['name']),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_house_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    if not participant:
        await query.edit_message_text(t('en', 'error_generic'))
        return
    lang = utils.get_lang(participant)

    house_id = query.data.replace('houseconfirm_', '')
    house = db.get_house_by_id(house_id)
    if not house:
        await query.edit_message_text(t('en', 'error_generic'))
        return

    # Pre-check capacity
    taken = db.get_house_occupancy(house_id)
    if taken >= house['capacity']:
        await query.edit_message_text(t(lang, 'house_full_msg'))
        return

    db.create_reservation(house_id, participant['id'])

    # Post-insert recheck: two users may have passed the pre-check simultaneously.
    # If we're now over capacity, delete the reservation just created and tell the user.
    taken_after = db.get_house_occupancy(house_id)
    if taken_after > house['capacity']:
        db.delete_reservation(participant['id'])
        await query.edit_message_text(t(lang, 'house_full_msg'))
        return

    await query.edit_message_text(
        t(lang, 'house_reserved', name=house['name']),
        parse_mode=ParseMode.MARKDOWN
    )


def get_housing_handlers() -> list:
    return [
        # Entry point: reply-keyboard button press → message with button text
        MessageHandler(filters.Text(_HOUSING_TEXTS), handle_housing_menu),
        # Sub-flow: inline buttons inside the housing sub-menu message
        CallbackQueryHandler(handle_housing_yes,       pattern='^menu_housing_yes$'),
        CallbackQueryHandler(handle_housing_no,        pattern='^menu_housing_no$'),
        CallbackQueryHandler(handle_house_select,      pattern='^house_[0-9a-f-]+$'),
        CallbackQueryHandler(handle_house_confirm,     pattern='^houseconfirm_[0-9a-f-]+$'),
    ]
