from datetime import timedelta, datetime

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.models import SlotType, TimeSlot, User
from utils.config import ADMIN_TELEGRAM_ID
from utils.decorators import with_db_session
from utils.utils import validate_time_slot, parse_time_slot
from utils.db_queries import get_or_create_user, save_time_slot, find_matching_offers
from apscheduler.schedulers.asyncio import AsyncIOScheduler

ASK_HELP_TIME_SLOTS, CONFIRM_MEETING = range(2)
scheduler = AsyncIOScheduler()
scheduler.start()


@with_db_session
async def ask_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Пожалуйста, укажите время, когда вам нужна помощь в формате YYYY-MM-DD HH:MM-HH:MM. '
        'Например, 2024-06-20 09:00-12:00'
    )
    return ASK_HELP_TIME_SLOTS


@with_db_session
async def save_ask_help_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_slot_text = update.message.text
    telegram_id = update.message.from_user.id
    telegram_username = update.message.from_user.username

    if validate_time_slot(time_slot_text):
        start_time, end_time = parse_time_slot(time_slot_text)

        session = context.chat_data['db_session']
        user = await get_or_create_user(session, telegram_id, telegram_username)
        await save_time_slot(session, user, start_time, end_time, slot_type=SlotType.REQUEST)
        await session.commit()
        matching_slots = await find_matching_offers(session, start_time, end_time)

        if matching_slots:
            matching_text = '\n'.join([
                f'@{slot.user.telegram_username} ({slot.start_time.strftime("%H:%M")}-{slot.end_time.strftime("%H:%M")})'
                for slot in matching_slots
            ])
            keyboard = [
                [
                    InlineKeyboardButton(
                        f'{slot.user.telegram_username} '
                        f'({slot.start_time.strftime("%H:%M")}-{slot.end_time.strftime("%H:%M")})',
                        callback_data=f"{slot.user.id}|{slot.start_time.isoformat()}|{slot.end_time.isoformat()}")
                ]
                for slot in matching_slots
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f'Нашёл помощников на выбранное время:\n\n{matching_text}\n\n'
                'Свяжитесь с ними, а после нажмите кнопку с пользователем, с которым удалось договориться:',
                reply_markup=reply_markup
            )
            return CONFIRM_MEETING
        else:
            await update.message.reply_text(
                'К сожалению, на указанное время никого нет. '
                'Продолжаю искать. Я уведомлю вас, как только кто-то найдётся.'
            )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            'Неверный формат. Пожалуйста, укажите время в формате YYYY-MM-DD HH:MM-HH:MM. '
            'Например, 2024-06-20 09:00-12:00'
        )
        return ASK_HELP_TIME_SLOTS


@with_db_session
async def confirm_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data.split('|')
    helper_id = int(callback_data[0])
    start_time = callback_data[1]
    end_time = callback_data[2]
    requester_id = query.from_user.id
    session = context.chat_data['db_session']

    start_time = datetime.fromisoformat(start_time)
    end_time = datetime.fromisoformat(end_time)

    helper_slot = await session.execute(
        select(TimeSlot)
        .filter_by(user_id=helper_id, start_time=start_time, end_time=end_time, type=SlotType.OFFER)
        .options(joinedload(TimeSlot.user))
    )
    helper_slot = helper_slot.scalars().first()

    requester_slot = None
    if helper_slot:
        requester_slot = await session.execute(
            select(TimeSlot)
            .join(User, TimeSlot.user_id == User.id)
            .filter(
                User.telegram_id == requester_id,
                TimeSlot.type == SlotType.REQUEST,
                or_(
                    and_(TimeSlot.start_time <= helper_slot.start_time, TimeSlot.end_time >= helper_slot.start_time),
                    and_(TimeSlot.start_time <= helper_slot.end_time, TimeSlot.end_time >= helper_slot.end_time),
                    and_(TimeSlot.start_time >= helper_slot.start_time, TimeSlot.end_time <= helper_slot.end_time),
                    and_(TimeSlot.start_time <= helper_slot.start_time, TimeSlot.end_time >= helper_slot.end_time),
                )
            )
            .order_by(TimeSlot.created.desc())
            .options(joinedload(TimeSlot.user))
        )
        requester_slot = requester_slot.scalars().first()
        if requester_slot:
            requester_slot.matched = True
            requester_slot.matched_user_id = helper_slot.user_id
            session.add(requester_slot)
            await session.commit()
    if helper_slot and requester_slot:
        helper_user = await session.execute(select(User).filter_by(id=helper_id))
        helper_user = helper_user.scalars().first()
        requester_user = await session.execute(select(User).filter_by(telegram_id=requester_id))
        requester_user = requester_user.scalars().first()

        if helper_user and requester_user:
            meeting_time = max(helper_slot.end_time, requester_slot.end_time) + timedelta(hours=1)
            scheduler.add_job(
                check_meeting_status, 'date', run_date=meeting_time, args=[
                    requester_id, helper_id, session, context
                ]
            )

            await query.edit_message_text(
                f'Вы выбрали помощь от пользователя @{helper_user.telegram_username}.\n'
                f'Слот помощника: {helper_slot.start_time.strftime("%Y-%m-%d %H:%M")} - '
                f'{helper_slot.end_time.strftime("%H:%M")}\n'
                f'Ваш слот: {requester_slot.start_time.strftime("%Y-%m-%d %H:%M")} - '
                f'{requester_slot.end_time.strftime("%H:%M")}\n'
                f'Мы напомним вам через час после встречи для подтверждения.'
            )
        else:
            await query.edit_message_text('Ошибка при подтверждении встречи. Пользователь не найден.')
    else:
        await query.edit_message_text('Ошибка при подтверждении встречи. Слот не найден.')


async def check_meeting_status(requester_id, helper_id, session, context):
    requester = await session.execute(select(User).filter_by(telegram_id=requester_id))
    helper = await session.execute(select(User).filter_by(id=helper_id))
    requester = requester.scalars().first()
    helper = helper.scalars().first()

    if requester and helper:
        keyboard = [
            [InlineKeyboardButton('Да', callback_data=f'confirm_yes_{requester_id}_{helper_id}'),
             InlineKeyboardButton('Нет', callback_data=f'confirm_no_{requester_id}_{helper_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(requester.telegram_id,
                                       f'Удалось ли вам договориться с пользователем @{helper.telegram_username} ()? '
                                       f'Пожалуйста, выберите "Да" или "Нет":',
                                       reply_markup=reply_markup)
        await context.bot.send_message(helper.telegram_id,
                                       f'Удалось ли вам договориться с пользователем @{requester.telegram_username}? '
                                       f'Пожалуйста, выберите: "Да" или "Нет":',
                                       reply_markup=reply_markup)


@with_db_session
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    confirmation = data[1]
    requester_id = int(data[2])
    helper_id = int(data[3])
    session: AsyncSession = context.chat_data['db_session']

    requester_slot_result = await session.execute(
        select(TimeSlot).join(
            User,
            TimeSlot.user_id == User.id
        ).filter(
            User.telegram_id == requester_id,
            TimeSlot.type == SlotType.REQUEST,
            TimeSlot.matched == True,
            TimeSlot.matched_user_id == helper_id
        ).order_by(TimeSlot.created.desc())
    )
    requester_slot = requester_slot_result.scalars().first()

    requester_result = await session.execute(select(User).filter_by(telegram_id=requester_id))
    helper_result = await session.execute(select(User).filter_by(id=helper_id))
    requester = requester_result.scalars().first()
    helper = helper_result.scalars().first()

    if requester_slot:
        helper_slot_result = await session.execute(
            select(TimeSlot).filter(
                TimeSlot.user_id == helper_id,
                TimeSlot.type == SlotType.OFFER,
                or_(
                    and_(TimeSlot.start_time <= requester_slot.start_time, TimeSlot.end_time >= requester_slot.start_time),
                    and_(TimeSlot.start_time <= requester_slot.end_time, TimeSlot.end_time >= requester_slot.end_time),
                    and_(TimeSlot.start_time >= requester_slot.start_time, TimeSlot.end_time <= requester_slot.end_time),
                    and_(TimeSlot.start_time <= requester_slot.start_time, TimeSlot.end_time >= requester_slot.end_time),
                )
            ).order_by(TimeSlot.start_time)
        )
        helper_slot = helper_slot_result.scalars().first()

        if helper_slot:
            helper_slot.matched = True
            helper_slot.matched_user_id = requester.id
            session.add(helper_slot)
            await session.commit()

    if confirmation == "yes":
        await query.edit_message_text('Спасибо за подтверждение! Рады, что вы смогли помочь друг другу.')
    else:
        await query.edit_message_text('Похоже, что что-то пошло не так. Я сообщу модератору для проверки.')
        if requester and helper and requester_slot:
            await context.bot.send_message(
                ADMIN_TELEGRAM_ID,
                f'Проблема с подтверждением встречи.\n\n'
                f'Запросил помощь: @{requester.telegram_username}.\n'
                f'Предложил помощь: @{helper.telegram_username}.\n\n'
                f'Слот: {requester_slot.start_time.strftime("%Y-%m-%d %H:%M")} - '
                f'{requester_slot.end_time.strftime("%H:%M")}'
            )
