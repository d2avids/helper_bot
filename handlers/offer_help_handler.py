from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.models import SlotType
from utils.decorators import with_db_session
from utils.utils import validate_time_slot, parse_time_slot
from utils.db_queries import save_time_slot, get_or_create_user, find_matching_requests

ASK_TIME_SLOTS = range(1)


@with_db_session
async def offer_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Пожалуйста, укажите время, когда вы готовы помочь в формате YYYY-MM-DD HH:MM-HH:MM. '
        'Например, 2024-06-20 09:00-12:00'
    )
    return ASK_TIME_SLOTS


@with_db_session
async def save_offer_help_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_slot_text = update.message.text
    telegram_id = update.message.from_user.id
    telegram_username = update.message.from_user.username

    if validate_time_slot(time_slot_text):
        start_time, end_time = parse_time_slot(time_slot_text)

        session = context.chat_data['db_session']
        user = await get_or_create_user(session, telegram_id, telegram_username)
        await save_time_slot(session, user, start_time, end_time, slot_type=SlotType.OFFER)

        matching_requests = await find_matching_requests(session, start_time, end_time)
        for request in matching_requests:
            matching_text = '\n'.join([
                f'@{slot.user.telegram_username} ({slot.start_time.strftime("%H:%M")}-{slot.end_time.strftime("%H:%M")})'
                for slot in matching_requests
            ])
            keyboard = [
                [
                    InlineKeyboardButton(
                        f'{slot.user.telegram_username} '
                        f'({slot.start_time.strftime("%H:%M")}-{slot.end_time.strftime("%H:%M")})',
                        callback_data=f"{slot.user.id}|{slot.start_time.isoformat()}|{slot.end_time.isoformat()}")
                ]
                for slot in matching_requests
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                request.user.telegram_id,
                f'Нашёл помощника на выбранное время:\n\n'
                f'{matching_text}\n\n'
                f'Пожалуйста, выберите если удалось договориться:',
                reply_markup=reply_markup
            )

        await update.message.reply_text(f'Вы указали временной слот: {time_slot_text}')
        return ConversationHandler.END

    else:
        await update.message.reply_text(
            'Неверный формат. Пожалуйста, укажите время в формате YYYY-MM-DD HH:MM-HH:MM. '
            'Например, 2024-06-20 09:00-12:00'
        )
        return ASK_TIME_SLOTS
