from sqlalchemy import select

from database.models import User, TimeSlot, SlotType


async def save_time_slot(session, user, start_time, end_time, slot_type):
    time_slot = TimeSlot(start_time=start_time, end_time=end_time, type=slot_type, user=user)
    session.add(time_slot)
    await session.commit()
    await session.refresh(time_slot)
    return time_slot


async def get_or_create_user(session, telegram_id, telegram_username):
    result = await session.execute(select(User).filter_by(telegram_id=telegram_id))
    user = result.scalars().first()
    if not user:
        user = User(telegram_id=telegram_id, telegram_username=telegram_username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def find_matching_offers(session, start_time, end_time):
    offers = await session.execute(
        select(TimeSlot).filter(
            TimeSlot.start_time <= end_time,
            TimeSlot.end_time >= start_time,
            TimeSlot.type == SlotType.OFFER,
            TimeSlot.matched == False,
        )
    )
    return offers.scalars().all()


async def find_matching_requests(session, start_time, end_time):
    requests = await session.execute(
        select(TimeSlot).filter(
            TimeSlot.start_time <= end_time,
            TimeSlot.end_time >= start_time,
            TimeSlot.type == SlotType.REQUEST,
            TimeSlot.matched == False,
        )
    )
    return requests.scalars().all()
