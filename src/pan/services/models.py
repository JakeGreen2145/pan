import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pan.services.database import Base


class UserRole(enum.StrEnum):
    OWNER = "owner"
    PRIMARY = "primary"
    TENANT = "tenant"


class ApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    discord_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(default=UserRole.TENANT)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    tenant_profile: Mapped["Tenant | None"] = relationship(back_populates="user", uselist=False)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    unit: Mapped[str] = mapped_column(String(50))
    rent_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    lease_start: Mapped[date]
    lease_end: Mapped[date]
    late_fee_flat: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    late_fee_daily: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    grace_period_days: Mapped[int] = mapped_column(default=5)
    is_active: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User] = relationship(back_populates="tenant_profile")
    payments: Mapped[list["RentPayment"]] = relationship(
        back_populates="tenant", order_by="RentPayment.period_start.desc()"
    )


class RentPayment(Base):
    __tablename__ = "rent_payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    date_paid: Mapped[date]
    period_start: Mapped[date]
    period_end: Mapped[date]
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="payments")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_domain: Mapped[str] = mapped_column(String(50), index=True)
    action_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(1000))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ApprovalStatus] = mapped_column(default=ApprovalStatus.PENDING, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(100))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None]
