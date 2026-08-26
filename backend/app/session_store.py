import os
from datetime import datetime, timezone
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from .models import Base, Session as DBSession, PromptRecord

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if os.getenv("ENVIRONMENT") == "production" or os.getenv("VERCEL") == "1":
        raise RuntimeError("DATABASE_URL environment variable is required in production.")
    DATABASE_URL = "sqlite:///./prompt_classifier.db"

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_or_create_session(session_id: str, db: Session | None = None) -> DBSession:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            session = DBSession(session_id=session_id)
            db.add(session)
            db.commit()
            db.refresh(session)
        db.expunge(session)
        return session
    finally:
        if close_db:
            db.close()

def add_prompt_record(
    session_id: str,
    prompt: str,
    classification: str,
    subtype: str | None,
    confidence: float,
    reasoning: str,
    latency_ms: int | None = None,
    total_tokens: int | None = None,
    explanation_details: str | None = None,
    reflection_prompt: str | None = None,
    classifier_version: str | None = "2.0.0",
    db: Session | None = None
) -> PromptRecord:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        get_or_create_session(session_id, db=db)
        record = PromptRecord(
            session_id=session_id,
            prompt=prompt,
            classification=classification,
            subtype=subtype,
            confidence=confidence,
            reasoning=reasoning,
            latency_ms=latency_ms,
            total_tokens=total_tokens,
            explanation_details=explanation_details,
            reflection_prompt=reflection_prompt,
            classifier_version=classifier_version,
            created_at=datetime.now(timezone.utc)
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        db.expunge(record)
        return record
    finally:
        if close_db:
            db.close()

def get_session_history(session_id: str, db: Session | None = None) -> list[PromptRecord]:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        records = (
            db.query(PromptRecord)
            .filter(PromptRecord.session_id == session_id)
            .order_by(PromptRecord.created_at.asc())
            .all()
        )
        for r in records:
            db.expunge(r)
        return records
    finally:
        if close_db:
            db.close()

def get_recent_session_history(session_id: str, cutoff: datetime, db: Session | None = None) -> list[PromptRecord]:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        lookup_cutoff = cutoff.astimezone(timezone.utc).replace(tzinfo=None) if cutoff.tzinfo else cutoff
        records = (
            db.query(PromptRecord)
            .filter(
                PromptRecord.session_id == session_id,
                PromptRecord.created_at >= lookup_cutoff
            )
            .order_by(PromptRecord.created_at.asc())
            .all()
        )
        for r in records:
            db.expunge(r)
        return records
    finally:
        if close_db:
            db.close()

def clear_session_history(session_id: str, db: Session | None = None) -> None:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        db.query(PromptRecord).filter(PromptRecord.session_id == session_id).delete()
        db.commit()
    finally:
        if close_db:
            db.close()

def get_cached_prompt_record(
    prompt: str,
    classifier_version: str | None = "2.0.0",
    max_age_seconds: int = 86400,
    db: Session | None = None
) -> PromptRecord | None:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        from sqlalchemy import func
        normalized = prompt.strip().lower()
        query = db.query(PromptRecord).filter(
            func.lower(func.trim(PromptRecord.prompt)) == normalized
        )
        if classifier_version is not None:
            query = query.filter(PromptRecord.classifier_version == classifier_version)
            
        record = query.order_by(PromptRecord.created_at.desc()).first()
        if record:
            if record.created_at:
                age = (datetime.now(timezone.utc) - record.created_at.replace(tzinfo=timezone.utc)).total_seconds()
                if age > max_age_seconds:
                    return None
            db.expunge(record)
        return record
    finally:
        if close_db:
            db.close()
