"""Idempotent demo data: `python -m app.seed`. Safe to run repeatedly."""

from pathlib import Path

from sqlalchemy import select

from app.core.security import hash_password
from app.db import SessionLocal, init_db
from app.models import Document, Role, Ticket, User
from app.services.ingestion import ingest_document
from app.services.storage import get_storage
from app.services.triage import triage_ticket

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
DEMO_PASSWORD = "Password123!"
USERS = [
    ("admin@helpdesk.io", "Asha Admin", Role.admin),
    ("agent@helpdesk.io", "Arjun Agent", Role.agent),
    ("employee@helpdesk.io", "Esha Employee", Role.employee),
]
TICKETS = [
    ("Locked out of my account",
     "I entered the wrong password too many times and now I can't log in to email. Need access urgently for a client call."),
    ("Expense claim not paid",
     "I submitted my travel reimbursement on the 25th but it was not in this month's payroll. When will it be paid?"),
    ("Need a second monitor for home", "Requesting a monitor and keyboard for my remote work days."),
]


def run() -> None:
    init_db()
    with SessionLocal() as db:
        users = {}
        for email, name, role in USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, name=name, role=role, hashed_password=hash_password(DEMO_PASSWORD))
                db.add(user)
                db.commit()
            users[role] = user

        for path in sorted(SEED_DIR.glob("*.md")):
            title = path.read_text().splitlines()[0].lstrip("# ").strip()
            if db.scalar(select(Document).where(Document.title == title)):
                continue
            doc = Document(title=title, filename=path.name, uploaded_by=users[Role.admin].id,
                           storage_key=get_storage().put(path.name, path.read_bytes()))
            db.add(doc)
            db.commit()
            ingest_document(db, doc.id)
            print(f"ingested {title}: {doc.chunk_count} chunks")

        employee = users[Role.employee]
        for title, description in TICKETS:
            if db.scalar(select(Ticket).where(Ticket.title == title)):
                continue
            ticket = Ticket(title=title, description=description, created_by=employee.id)
            db.add(ticket)
            db.commit()
            triage_ticket(db, ticket.id)
            print(f"ticket '{title}' -> {ticket.category}/{ticket.priority}")
    print(f"Demo users (password {DEMO_PASSWORD}): " + ", ".join(u[0] for u in USERS))


if __name__ == "__main__":
    run()
