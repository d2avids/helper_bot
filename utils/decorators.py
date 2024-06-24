from functools import wraps
from database.engine import session_maker


def with_db_session(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        async with session_maker() as session:
            context.chat_data['db_session'] = session
            return await func(update, context, *args, **kwargs)
    return wrapped
