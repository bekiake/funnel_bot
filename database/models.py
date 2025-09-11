import os
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, BigInteger, func, Boolean, Integer, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional

# PostgreSQL JSONB support
try:
    from sqlalchemy.dialects.postgresql import JSONB
    database_url = os.getenv("DATABASE_URL", "")
    if "postgresql" in database_url:
        JSON_TYPE = JSONB
    else:
        JSON_TYPE = JSON
except ImportError:
    JSON_TYPE = JSON


class Base(DeclarativeBase):
    created: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=True)
    phone: Mapped[str] = mapped_column(String(13), nullable=True)
    
    # Связи
    funnel_statistics = relationship("FunnelStatistic", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")


class Funnel(Base):
    __tablename__ = 'funnel'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(50), unique=True)  # ключ для ссылки
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Связи
    steps = relationship("FunnelStep", back_populates="funnel", cascade="all, delete-orphan")
    statistics = relationship("FunnelStatistic", back_populates="funnel")


class FunnelStep(Base):
    __tablename__ = 'funnel_step'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    funnel_id: Mapped[int] = mapped_column(ForeignKey('funnel.id'))
    step_number: Mapped[int] = mapped_column(Integer)  # порядок шага
    
    # Типы контента
    content_type: Mapped[str] = mapped_column(String(20))  # photo, video, audio, document, text
    content_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # file_id или текст
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Кнопка для перехода к следующему шагу
    button_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Связи
    funnel = relationship("Funnel", back_populates="steps")


class FunnelStatistic(Base):
    __tablename__ = 'funnel_statistic'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.user_id'))
    funnel_id: Mapped[int] = mapped_column(ForeignKey('funnel.id'))
    
    current_step: Mapped[int] = mapped_column(Integer, default=0)  # текущий шаг
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Детальная статистика по шагам (JSONB для PostgreSQL, JSON для SQLite)
    step_statistics: Mapped[Optional[dict]] = mapped_column(JSON_TYPE, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="funnel_statistics")
    funnel = relationship("Funnel", back_populates="statistics")


class SubscriptionPlan(Base):
    __tablename__ = 'subscription_plan'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    duration_days: Mapped[int] = mapped_column(Integer)  # продолжительность в днях
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2))
    price_uzs: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)  # ID канала для подписки
    
    # Связи
    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = 'subscription'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.user_id'))
    plan_id: Mapped[int] = mapped_column(ForeignKey('subscription_plan.id'))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    invite_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    payment_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Связи
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")


