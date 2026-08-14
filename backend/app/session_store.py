import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.models import Base, Session as DBSession, PromptRecord

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prompt_classifier.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_or_create_session(session_id: str) -> DBSession:
    db = SessionLocal()
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
        db.close()

def add_prompt_record(
    session_id: str,
    prompt: str,
    classification: str,
    subtype: str | None,
    confidence: float,
    reasoning: str
) -> PromptRecord:
    get_or_create_session(session_id)
    db = SessionLocal()
    try:
        record = PromptRecord(
            session_id=session_id,
            prompt=prompt,
            classification=classification,
            subtype=subtype,
            confidence=confidence,
            reasoning=reasoning,
            created_at=datetime.now(timezone.utc)
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        db.expunge(record)
        return record
    finally:
        db.close()

def get_session_history(session_id: str) -> list[PromptRecord]:
    db = SessionLocal()
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
        db.close()

def clear_session_history(session_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(PromptRecord).filter(PromptRecord.session_id == session_id).delete()
        db.commit()
    finally:
        db.close()
