from sqlalchemy import String, JSON, Double, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class ReviewPackage(Base):
    __tablename__ = 'review_packages'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    dataset_name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(12), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='assigned')
    vendor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    claimed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    submitted_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    closed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    source_checksum: Mapped[str] = mapped_column(String(64))
    accepted_submission_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_dataset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
class ReviewItem(Base):
    __tablename__ = 'review_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey('review_packages.id'))
    seq: Mapped[int] = mapped_column(Integer)
    alias: Mapped[str] = mapped_column(String(40), unique=True)
    asset: Mapped[str] = mapped_column(String(160))
    model: Mapped[str] = mapped_column(String(120))
    km: Mapped[float] = mapped_column(Double)
    failed: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[int | None] = mapped_column(Integer, nullable=True)
class ReviewSubmission(Base):
    __tablename__ = 'review_submissions'
    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey('review_packages.id'))
    vendor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Double)
    __table_args__ = (UniqueConstraint('package_id', 'idempotency_key', name='uq_submission_key'),)
