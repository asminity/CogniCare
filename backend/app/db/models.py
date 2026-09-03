from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    diagnosis: Mapped[str] = mapped_column(String(240), nullable=False)
    care_needs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    journeys: Mapped[list["CareJourney"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    simulations: Mapped[list["Simulation"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    shocks: Mapped[list["PolicyShock"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(160), nullable=False)
    member_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    network_name: Mapped[str] = mapped_column(String(160), nullable=False)
    deductible_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    out_of_pocket_max_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    rules: Mapped[list["PolicyRule"]] = relationship(back_populates="policy", cascade="all, delete-orphan")
    simulations: Mapped[list["Simulation"]] = relationship(back_populates="policy", cascade="all, delete-orphan")
    shocks: Mapped[list["PolicyShock"]] = relationship(back_populates="policy", cascade="all, delete-orphan")


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(80), nullable=False)
    service_name: Mapped[str] = mapped_column(String(160), nullable=False)
    in_network: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_authorization: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    coverage_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    copay_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    rule_value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    policy: Mapped["Policy"] = relationship(back_populates="rules")


class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    network_names: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    services: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    emergency_capable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="hospital")


class CareJourney(Base):
    __tablename__ = "care_journeys"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    condition: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="journeys")
    events: Mapped[list["CareEvent"]] = relationship(back_populates="journey", cascade="all, delete-orphan")
    shocks: Mapped[list["PolicyShock"]] = relationship(back_populates="journey")
    simulations: Mapped[list["Simulation"]] = relationship(back_populates="journey")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="journey")


class CareEvent(Base):
    __tablename__ = "care_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    journey_id: Mapped[int] = mapped_column(ForeignKey("care_journeys.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="planned")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    journey: Mapped["CareJourney"] = relationship(back_populates="events")
    shocks: Mapped[list["PolicyShock"]] = relationship(back_populates="event")


class PolicyShock(Base):
    __tablename__ = "policy_shocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    journey_id: Mapped[int | None] = mapped_column(ForeignKey("care_journeys.id", ondelete="SET NULL"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("care_events.id", ondelete="SET NULL"))
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    patient: Mapped["Patient"] = relationship(back_populates="shocks")
    policy: Mapped["Policy"] = relationship(back_populates="shocks")
    journey: Mapped["CareJourney"] = relationship(back_populates="shocks")
    event: Mapped["CareEvent | None"] = relationship(back_populates="shocks")


class Simulation(Base):
    __tablename__ = "simulations"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    journey_id: Mapped[int | None] = mapped_column(ForeignKey("care_journeys.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="simulations")
    policy: Mapped["Policy"] = relationship(back_populates="simulations")
    journey: Mapped["CareJourney | None"] = relationship(back_populates="simulations")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="simulation")


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    journey_id: Mapped[int | None] = mapped_column(ForeignKey("care_journeys.id", ondelete="SET NULL"))
    simulation_id: Mapped[int | None] = mapped_column(ForeignKey("simulations.id", ondelete="SET NULL"))
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    compatibility_score: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_cents: Mapped[int | None] = mapped_column(Integer)
    patient: Mapped["Patient"] = relationship(back_populates="recommendations")
    journey: Mapped["CareJourney | None"] = relationship(back_populates="recommendations")
    simulation: Mapped["Simulation | None"] = relationship(back_populates="recommendations")
    hospital: Mapped["Hospital | None"] = relationship(back_populates="recommendations")