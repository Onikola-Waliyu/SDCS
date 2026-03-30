from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from sqlalchemy import desc

from app.db.models import Transaction, get_session
from datetime import datetime, timezone, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(request: Request):
    """Render the main dashboard HTML template."""
    return templates.TemplateResponse(
        request=request, name="dashboard.html"
    )

@router.get("/api/transactions")
async def api_get_transactions(
    session: Session = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
    search: str = None
):
    """Return JSON list of transactions, optionally filtered by search term."""
    query = select(Transaction).order_by(desc(Transaction.created_at))
    
    if search:
        search_term = f"%{search}%"
        # Search by recorded_by, item name, or customer name
        query = query.where(
            (Transaction.recorded_by.ilike(search_term)) |
            (Transaction.item.ilike(search_term)) |
            (Transaction.customer.ilike(search_term))
        )
        
    transactions = session.exec(query.offset(offset).limit(limit)).all()
    
    # Get total count for pagination info
    count_query = select(func.count(Transaction.id))
    if search:
        count_query = count_query.where(
            (Transaction.recorded_by.ilike(search_term)) |
            (Transaction.item.ilike(search_term)) |
            (Transaction.customer.ilike(search_term))
        )
    total_count = session.exec(count_query).one()
    
    return {
        "items": transactions,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }

@router.get("/api/stats")
async def api_get_stats(session: Session = Depends(get_session)):
    """Return JSON summary statistics for the dashboard."""
    # Total revenue
    total_rev_query = select(func.sum(Transaction.amount))
    total_revenue = session.exec(total_rev_query).one() or 0.0
    
    # Total transactions
    total_tx_query = select(func.count(Transaction.id))
    total_transactions = session.exec(total_tx_query).one() or 0
    
    # Unique active businesses
    unique_cust_query = select(func.count(func.distinct(Transaction.business_id)))
    total_customers = session.exec(unique_cust_query).one() or 0
    
    # Today's revenue
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_rev_query = select(func.sum(Transaction.amount)).where(Transaction.created_at >= today_start)
    today_revenue = session.exec(today_rev_query).one() or 0.0

    # Trend vs yesterday (calculate yesterday's revenue)
    yesterday_start = today_start - timedelta(days=1)
    yesterday_rev_query = select(func.sum(Transaction.amount)).where(
        Transaction.created_at >= yesterday_start,
        Transaction.created_at < today_start
    )
    yesterday_revenue = session.exec(yesterday_rev_query).one() or 0.0
    
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
