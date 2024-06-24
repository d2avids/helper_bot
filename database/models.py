import enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, Column, Enum, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from utils.utils import get_current_datetime


class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=get_current_datetime)
    updated: Mapped[DateTime] = mapped_column(DateTime, default=get_current_datetime, onupdate=get_current_datetime)


class SlotType(enum.Enum):
    OFFER = 'offer'
    REQUEST = 'request'


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    telegram_username = Column(String(150), nullable=False)
    time_slots = relationship('TimeSlot', back_populates='user', foreign_keys='TimeSlot.user_id')


class TimeSlot(Base):
    __tablename__ = 'time_slot'

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    type = Column(Enum(SlotType), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship('User', back_populates='time_slots', foreign_keys=[user_id])
    matched = Column(Boolean, nullable=False, default=False)
    matched_user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    matched_user = relationship('User', foreign_keys=[matched_user_id])
