from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.ratelimit import rate_limit
from app.core.security import CurrentUser, DbSession, require_roles
from app.models import Role, Ticket, TicketStatus, User
from app.schemas import Page, TicketIn, TicketOut, TicketUpdate
from app.services.events import get_event_bus

router = APIRouter(prefix="/api/tickets", tags=["tickets"])
Staff = Annotated[User, Depends(require_roles(Role.admin, Role.agent))]


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
def create_ticket(body: TicketIn, user: CurrentUser, db: DbSession):
    ticket = Ticket(title=body.title.strip(), description=body.description.strip(), created_by=user.id)
    db.add(ticket)
    db.commit()
    get_event_bus().publish("ticket.created", {"ticket_id": ticket.id})
    db.refresh(ticket)
    return ticket


@router.get("", response_model=Page[TicketOut])
def list_tickets(
    user: CurrentUser,
    db: DbSession,
    status_: Annotated[TicketStatus | None, Query(alias="status")] = None,
    category: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query = select(Ticket)
    if user.role == Role.employee:  # row-level authorisation: employees only see their own tickets
        query = query.where(Ticket.created_by == user.id)
    if status_:
        query = query.where(Ticket.status == status_)
    if category:
        query = query.where(Ticket.category == category)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Ticket.created_at.desc(), Ticket.id.desc())
                       .offset((page - 1) * size).limit(size)).all()
    return Page[TicketOut](items=items, total=total or 0, page=page, size=size)


def _get_visible(db, user: User, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    # 404 (not 403) for other people's tickets so IDs can't be probed.
    if ticket is None or (user.role == Role.employee and ticket.created_by != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, user: CurrentUser, db: DbSession):
    return _get_visible(db, user, ticket_id)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, body: TicketUpdate, user: Staff, db: DbSession):
    ticket = _get_visible(db, user, ticket_id)
    ticket.status = body.status
    db.commit()
    return ticket


@router.post("/{ticket_id}/retriage", response_model=TicketOut, status_code=status.HTTP_202_ACCEPTED)
def retriage(ticket_id: int, user: Staff, db: DbSession):
    ticket = _get_visible(db, user, ticket_id)
    ticket.triage_status = "pending"
    db.commit()
    get_event_bus().publish("ticket.created", {"ticket_id": ticket.id})
    db.refresh(ticket)
    return ticket
