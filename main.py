import asyncio
import logging
import os
from logging.handlers import TimedRotatingFileHandler
import nest_asyncio
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
nest_asyncio.apply()

from telegram import ReplyKeyboardMarkup, Update, KeyboardButton
from telegram.ext import (ApplicationBuilder,
                          CommandHandler, ConversationHandler,
                          ContextTypes, MessageHandler,
                          filters, CallbackQueryHandler)

from database.engine import create_db
from handlers.ask_help_handler import ASK_HELP_TIME_SLOTS, CONFIRM_MEETING, save_ask_help_time_slots, confirm_meeting, \
    ask_help_handler, handle_confirmation
from handlers.offer_help_handler import offer_help_handler, save_offer_help_time_slots, ASK_TIME_SLOTS


class ExcludeLoggerFilter(logging.Filter):
    def __init__(self, name):
        self.name = name

    def filter(self, record):
        return not record.name.startswith(self.name)


LOG_DIR = 'logs'
logging.basicConfig(level=logging.DEBUG)
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, 'bot.log')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = TimedRotatingFileHandler(log_file, when='midnight', interval=1, backupCount=3)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
exclude_httpcore_filter = ExcludeLoggerFilter('httpcore.http11')
handler.addFilter(exclude_httpcore_filter)
handler.setFormatter(formatter)
logger.addHandler(handler)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
OFFER_HELP_ACTION = 'Помочь'
ASK_HELP_ACTION = 'Попросить помощь'
ACTIONS_BUTTONS = ReplyKeyboardMarkup([
    [KeyboardButton(OFFER_HELP_ACTION)],
    [KeyboardButton(ASK_HELP_ACTION)]
], resize_keyboard=True, one_time_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f'Привет! Чем могу помочь? Выберите действие: {OFFER_HELP_ACTION} или {ASK_HELP_ACTION}.',
        reply_markup=ACTIONS_BUTTONS,
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END


async def main():
    await create_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    start_handler = CommandHandler('start', start)
    ask_help_hndlr = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex(f'^{ASK_HELP_ACTION}$'), ask_help_handler)],
            states={
                ASK_HELP_TIME_SLOTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_ask_help_time_slots)],
                CONFIRM_MEETING: [CallbackQueryHandler(confirm_meeting)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
    offer_help_hndlr = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f'^{OFFER_HELP_ACTION}$'), offer_help_handler)],
        states={
            ASK_TIME_SLOTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_offer_help_time_slots)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    confirmation_handler = CallbackQueryHandler(
        handle_confirmation, pattern=r'^confirm_(yes|no)_\d+_\d+$'
    )
    app.add_handler(start_handler, 1)
    app.add_handler(ask_help_hndlr, 2)
    app.add_handler(offer_help_hndlr, 3)
    app.add_handler(confirmation_handler, 4)
    app.run_polling()


if __name__ == '__main__':
    asyncio.run(main())
