import os
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from sqlalchemy import desc

from app.db.models import Transaction, get_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
security = HTTPBasic()

def admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, os.getenv("ADMIN_USER", "admin"))
    correct_password = secrets.compare_digest(credentials.password, os.getenv("ADMIN_PASSWORD", "sdcs123!"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(request: Request, _=Depends(admin_auth)):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@router.get("/api/transactions")
async def api_get_transactions(
    session: Session = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
    search: str = None,
    _=Depends(admin_auth)
):
    query = select(Transaction).order_by(desc(Transaction.created_at))
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Transaction.recorded_by.ilike(search_term)) |
            (Transaction.item.ilike(search_term)) |
            (Transaction.customer.ilike(search_term)) |
            (Transaction.business_id.ilike(search_term))
        )
    transactions = session.exec(query.offset(offset).limit(limit)).all()
    count_query = select(func.count(Transaction.id))
    if search:
        count_query = count_query.where(
            (Transaction.recorded_by.ilike(search_term)) |
            (Transaction.item.ilike(search_term)) |
            (Transaction.customer.ilike(search_term)) |
            (Transaction.business_id.ilike(search_term))
        )
    total_count = session.exec(count_query).one()
    return {"items": transactions, "total": total_count, "limit": limit, "offset": offset}

@router.get("/api/stats")
async def api_get_stats(session: Session = Depends(get_session), _=Depends(admin_auth)):
    total_revenue = session.exec(select(func.sum(Transaction.amount))).one() or 0.0
    total_transactions = session.exec(select(func.count(Transaction.id))).one() or 0
    total_customers = session.exec(select(func.count(func.distinct(Transaction.business_id)))).one() or 0
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_revenue = session.exec(select(func.sum(Transaction.amount)).where(Transaction.created_at >= today_start)).one() or 0.0

    yesterday_start = today_start - timedelta(days=1)
    yesterday_revenue = session.exec(select(func.sum(Transaction.amount)).where(
        Transaction.created_at >= yesterday_start,
        Transaction.created_at < today_start
    )).one() or 0.0
    
    if yesterday_revenue > 0:
        trend_perc = ((today_revenue - yesterday_revenue) / yesterday_revenue) * 100
    else:
        trend_perc = 100.0 if today_revenue > 0 else 0.0
        
    return {
        "total_revenue": total_revenue,
        "total_transactions": total_transactions,
        "total_customers": total_customers,
        "today_revenue": today_revenue,
        "yesterday_revenue": yesterday_revenue,
        "trend_percentage": round(trend_perc, 1)
    }

@router.get("/api/admin/export/csv")
async def admin_export_csv(session: Session = Depends(get_session), _=Depends(admin_auth)):
    from app.utils.exporter import generate_transactions_csv
    statement = select(Transaction).order_by(Transaction.created_at.desc())
    transactions = session.exec(statement).all()
    csv_data = generate_transactions_csv(transactions)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sdcs_global_transactions.csv"}
    )

@router.get("/api/admin/export/pdf")
async def admin_export_pdf(session: Session = Depends(get_session), _=Depends(admin_auth)):
    statement = select(Transaction).order_by(desc(Transaction.created_at))
    rows = session.exec(statement).all()

    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "SDCS Master Admin - Global Sales Report", border=0, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d')} | Total Trx: {len(rows)}", border=0, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(30, 10, "Date", border=1, fill=True)
    pdf.cell(45, 10, "Item", border=1, fill=True)
    pdf.cell(15, 10, "Qty", border=1, fill=True)
    pdf.cell(30, 10, "Amount", border=1, fill=True)
    pdf.cell(35, 10, "Customer", border=1, fill=True)
    pdf.cell(35, 10, "Agent ID", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 7)
    total_amount = 0.0
    for tx in rows:
        total_amount += tx.amount
        pdf.cell(30, 8, tx.created_at.strftime("%Y-%m-%d %H:%M"), border=1)
        pdf.cell(45, 8, (tx.item[:25] + '..') if len(tx.item) > 27 else tx.item, border=1)
        qty_val = int(tx.quantity) if float(tx.quantity).is_integer() else tx.quantity
        pdf.cell(15, 8, f"{qty_val} {tx.unit}", border=1)
        pdf.cell(30, 8, f"N {tx.amount:,.2f}", border=1)
        cust = (tx.customer[:20] + '..') if tx.customer and len(tx.customer) > 22 else (tx.customer or "")
        pdf.cell(35, 8, cust, border=1)
        
        from app.db.models import User
        recorder = session.get(User, tx.recorded_by)
        agent_label = (recorder.name or tx.recorded_by) if recorder else tx.recorded_by
        agent = (agent_label[:20] + '..') if len(agent_label) > 22 else agent_label
        pdf.cell(35, 8, agent, border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"Global Gross Amount: N {total_amount:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = pdf.output()
    return Response(content=bytes(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=sdcs_global_report.pdf"})
