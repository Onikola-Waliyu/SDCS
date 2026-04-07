"""
User-facing routes: PIN authentication, owner dashboard, staff management.
Session is managed via a signed HttpOnly cookie containing the owner's phone number.
Dashboard access is restricted to OWNER role only.
"""
import bcrypt
import os
import csv
import io

from datetime import datetime, timezone, timedelta
from typing import Optional, Annotated

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlmodel import Session, select, func
from sqlalchemy import desc

from app.db.models import Business, Transaction, User, UserRole, UserState, get_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
SESSION_COOKIE = "gl_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

_signer = URLSafeTimedSerializer(SECRET_KEY)


# ── Session helpers ────────────────────────────────────────────────────────────

def _sign(phone: str) -> str:
    return _signer.dumps(phone)


def _unsign(token: str) -> Optional[str]:
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def _get_current_phone(gl_session: Optional[str] = Cookie(default=None)) -> Optional[str]:
    if not gl_session:
        return None
    return _unsign(gl_session)


def _require_owner(phone: Optional[str] = Depends(_get_current_phone), session: Session = Depends(get_session)) -> User:
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = session.get(User, phone)
    if not user or user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Owners only")
    return user


# ── Pages ──────────────────────────────────────────────────────────────────────

@router.get("/my-ledger", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None, gl_session: Optional[str] = Cookie(default=None)):
    """Show login page, or redirect if already authenticated."""
    if gl_session and _unsign(gl_session):
        return RedirectResponse("/my-ledger/dashboard", status_code=302)
    return templates.TemplateResponse(request=request, name="my_ledger_login.html", context={"error": error})


@router.get("/my-ledger/dashboard", response_class=HTMLResponse)
async def user_dashboard_page(request: Request, owner: User = Depends(_require_owner), session: Session = Depends(get_session)):
    """Render the owner's business dashboard."""
    business = session.get(Business, owner.business_id)
    return templates.TemplateResponse(
        request=request,
        name="my_ledger.html",
        context={"phone": owner.phone_number, "business_name": business.name if business else "My Business"},
    )


# ── Auth API ───────────────────────────────────────────────────────────────────

@router.post("/api/auth/login")
async def login(
    phone: Annotated[str, Form()],
    pin: Annotated[str, Form()],
    session: Session = Depends(get_session),
):
    phone = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    pin = pin.strip()

    user = session.get(User, phone)
    if not user or user.role != UserRole.OWNER:
        return RedirectResponse("/my-ledger?error=Dashboard+access+is+for+business+owners+only", status_code=303)
    if not user.pin_hash or not bcrypt.checkpw(pin.encode(), user.pin_hash.encode()):
        return RedirectResponse("/my-ledger?error=Invalid+phone+number+or+PIN", status_code=303)

    token = _sign(phone)
    response = RedirectResponse("/my-ledger/dashboard", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return response


@router.post("/api/auth/logout")
async def logout():
    response = RedirectResponse("/my-ledger", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ── Date range helper ──────────────────────────────────────────────────────────

def _date_range_for_period(period: str):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "today":
        return today_start, now
    elif period == "week":
        return today_start - timedelta(days=today_start.weekday()), now
    elif period == "month":
        return today_start.replace(day=1), now
    else:
        return None, None


# ── Business Data API (scoped to business_id) ──────────────────────────────────

@router.get("/api/my/stats")
async def my_stats(
    period: str = "all",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    owner: User = Depends(_require_owner),
    session: Session = Depends(get_session),
):
    start, end = _date_range_for_period(period)
    if from_date:
        start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
    if to_date:
        end = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) + timedelta(days=1)

    def make_query(agg):
        q = select(agg).where(Transaction.business_id == owner.business_id)
        if start:
            q = q.where(Transaction.created_at >= start)
        if end:
            q = q.where(Transaction.created_at < end)
        return q

    total_revenue = session.exec(make_query(func.sum(Transaction.amount))).one() or 0.0
    total_count   = session.exec(make_query(func.count(Transaction.id))).one() or 0
    avg_sale      = (total_revenue / total_count) if total_count else 0.0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_revenue = session.exec(
        select(func.sum(Transaction.amount)).where(
            Transaction.business_id == owner.business_id,
            Transaction.created_at >= today_start,
        )
    ).one() or 0.0

    return {
        "total_revenue": total_revenue,
        "total_transactions": total_count,
        "today_revenue": today_revenue,
        "avg_sale_value": avg_sale,
        "period": period,
    }


@router.get("/api/my/transactions")
async def my_transactions(
    period: str = "all",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search: Optional[str] = None,
    owner: User = Depends(_require_owner),
    session: Session = Depends(get_session),
):
    start, end = _date_range_for_period(period)
    if from_date:
        start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
    if to_date:
        end = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) + timedelta(days=1)

    q = select(Transaction).where(Transaction.business_id == owner.business_id)
    if start:
        q = q.where(Transaction.created_at >= start)
    if end:
        q = q.where(Transaction.created_at < end)
    if search:
        term = f"%{search}%"
        q = q.where(Transaction.item.ilike(term) | Transaction.customer.ilike(term))
    q = q.order_by(desc(Transaction.created_at))
    rows = session.exec(q).all()

    # Fetch recorded_by names for display
    result = []
    for tx in rows:
        recorder = session.get(User, tx.recorded_by)
        result.append({
            "id": tx.id,
            "item": tx.item,
            "quantity": int(tx.quantity) if float(tx.quantity).is_integer() else tx.quantity,
            "unit": tx.unit,
            "amount": tx.amount,
            "customer": tx.customer,
            "recorded_by": recorder.name or tx.recorded_by if recorder else tx.recorded_by,
            "created_at": tx.created_at.isoformat(),
        })

    total_revenue = sum(r["amount"] for r in result)
    return {"items": result, "total": len(result), "total_revenue": total_revenue}


@router.get("/api/my/export/csv")
async def my_export(
    period: str = "all",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    owner: User = Depends(_require_owner),
    session: Session = Depends(get_session),
):
    start, end = _date_range_for_period(period)
    if from_date:
        start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
    if to_date:
        end = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) + timedelta(days=1)

    q = select(Transaction).where(Transaction.business_id == owner.business_id)
    if start:
        q = q.where(Transaction.created_at >= start)
    if end:
        q = q.where(Transaction.created_at < end)
    rows = session.exec(q.order_by(desc(Transaction.created_at))).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Item", "Quantity", "Unit", "Amount (₦)", "Customer", "Recorded By"])
    for tx in rows:
        recorder = session.get(User, tx.recorded_by)
        recorder_label = recorder.name or tx.recorded_by if recorder else tx.recorded_by
        writer.writerow([
            tx.created_at.strftime("%Y-%m-%d %H:%M"),
            tx.item, tx.quantity, tx.unit, tx.amount, tx.customer or "", recorder_label
        ])
    buf.seek(0)
    filename = f"ledger_{period}_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/api/my/export/pdf")
async def my_export_pdf(
    period: str = "all",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    owner: User = Depends(_require_owner),
    session: Session = Depends(get_session),
):
    start, end = _date_range_for_period(period)
    if from_date:
        start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
    if to_date:
        end = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) + timedelta(days=1)

    q = select(Transaction).where(Transaction.business_id == owner.business_id)
    if start:
        q = q.where(Transaction.created_at >= start)
    if end:
        q = q.where(Transaction.created_at < end)
    rows = session.exec(q.order_by(desc(Transaction.created_at))).all()

    business = session.get(Business, owner.business_id)
    business_name = business.name if business else "SDCS Ledger"

    from fpdf import FPDF
    from fastapi.responses import Response

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"{business_name} - Sales Report", border=0, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, f"Period: {period.capitalize()} | Total Transactions: {len(rows)}", border=0, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(35, 10, "Date", border=1, fill=True)
    pdf.cell(60, 10, "Item", border=1, fill=True)
    pdf.cell(20, 10, "Qty", border=1, fill=True)
    pdf.cell(40, 10, "Amount", border=1, fill=True)
    pdf.cell(35, 10, "Recorded By", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    total_amount = 0.0
    for tx in rows:
        total_amount += tx.amount
        date_str = tx.created_at.strftime("%Y-%m-%d")
        item_str = (tx.item[:32] + '..') if len(tx.item) > 34 else tx.item
        recorder = session.get(User, tx.recorded_by)
        recorder_label = recorder.name or tx.recorded_by if recorder else tx.recorded_by
        phone_str = recorder_label[:14]
        
        pdf.cell(35, 10, date_str, border=1)
        pdf.cell(60, 10, item_str, border=1)
        
        qty_val = int(tx.quantity) if float(tx.quantity).is_integer() else tx.quantity
        pdf.cell(20, 10, f"{qty_val} {tx.unit}", border=1)
        
        pdf.cell(40, 10, f"N {tx.amount:,.2f}", border=1)
        pdf.cell(35, 10, phone_str, border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"Total Amount: N {total_amount:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = pdf.output()
    filename = f"ledger_{period}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return Response(content=bytes(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})


# ── Staff Management API ───────────────────────────────────────────────────────

@router.get("/api/my/staff")
async def list_staff(owner: User = Depends(_require_owner), session: Session = Depends(get_session)):
    """Returns all staff members for this owner's business."""
    statement = select(User).where(
        User.business_id == owner.business_id,
        User.phone_number != owner.phone_number,
    )
    staff = session.exec(statement).all()
    return {"staff": [{"phone": s.phone_number, "name": s.name, "role": s.role} for s in staff]}


@router.post("/api/my/staff")
async def add_staff(
    phone: Annotated[str, Form()],
    name: Annotated[Optional[str], Form()] = None,
    owner: User = Depends(_require_owner),
    session: Session = Depends(get_session),
):
    """Add a staff member to this owner's business via the web dashboard."""
    from app.services.whatsapp import send_whatsapp_message

    staff_phone = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    if not staff_phone.isdigit():
        raise HTTPException(status_code=400, detail="Invalid phone number format.")

    existing = session.get(User, staff_phone)
    if existing:
        if existing.business_id == owner.business_id:
            raise HTTPException(status_code=409, detail="This number is already in your team.")
        raise HTTPException(status_code=409, detail="This number is registered with another business.")

    business = session.get(Business, owner.business_id)
    staff = User(
        phone_number=staff_phone,
        business_id=owner.business_id,
        role=UserRole.STAFF,
        state=UserState.ACTIVE,
        name=name.strip() if name else None,
    )
    session.add(staff)
    session.commit()

    business_name = business.name if business else "your business"
    import asyncio
    asyncio.create_task(send_whatsapp_message(
        staff_phone,
        f"👋 You've been added as a sales agent for *{business_name}* on SDCS Ledger!\n\n"
        "You can start recording sales right away. Just send a message like:\n"
        "_\"Sold 3 bottles of oil for 6k\"_"
    ))
    return {"status": "ok", "phone": staff_phone}


@router.delete("/api/my/staff/{staff_phone}")
async def remove_staff(
    staff_phone: str,
    owner: User = Depends(_require_owner),
    session: Session = Depends(get_session),
):
    """Remove a staff member from this owner's business."""
    staff = session.get(User, staff_phone)
    if not staff or staff.business_id != owner.business_id:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    session.delete(staff)
    session.commit()
    return {"status": "ok"}
