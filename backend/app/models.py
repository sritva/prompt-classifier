from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Session(Base):
    __tablename__ = "sessions"
    
    session_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    records = relationship("PromptRecord", back_populates="session", cascade="all, delete-orphan")

class PromptRecord(Base):
    __tablename__ = "prompt_records"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    prompt = Column(String, nullable=False)
    classification = Column(String, nullable=False)  # "convergent" or "divergent"
    subtype = Column(String, nullable=True)  # "factual_lookup", "computation", "code_debugging", "decision_making", "other"
    confidence = Column(Float, nullable=False)
    reasoning = Column(String, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    explanation_details = Column(String, nullable=True)
    reflection_prompt = Column(String, nullable=True)
    classifier_version = Column(String, nullable=True, default="2.0.0")
    model = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    is_heuristic = Column(Boolean, nullable=True, default=False)
    is_cached = Column(Boolean, nullable=True, default=False)
    original_latency_ms = Column(Integer, nullable=True)
    original_total_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    session = relationship("Session", back_populates="records")
