"""
Tests for webhook command handlers (today, summary, undo, export).
Uses the shared SQLite fixtures from conftest.py.
"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlmodel import Session

from app.api.webhook import (
    send_daily_summary,
    send_all_time_summary,
    undo_last_transaction,
    process_incoming_message,
)
from app.db.models import Transaction
from app.utils.exporter import generate_transactions_csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_transaction(session: Session, **kwargs) -> Transaction:
    defaults = dict(phone_number="2340000000000", item="beans", quantity=1, unit="paint", amount=5000)
    defaults.update(kwargs)
    tx = Transaction(**defaults)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# today command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock)
async def test_today_with_transactions(mock_send, session):
    _add_transaction(session, phone_number="234111", amount=10000)
    _add_transaction(session, phone_number="234111", amount=5000)
    await send_daily_summary("234111", session)
    reply = mock_send.call_args[0][1]
    assert "₦15,000.00" in reply
    assert "2 transactions" in reply


@pytest.mark.asyncio
@patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock)
async def test_today_no_transactions(mock_send, session):
    await send_daily_summary("234_no_tx", session)
    reply = mock_send.call_args[0][1]
    assert "₦0.00" in reply
    assert "0 transactions" in reply


# ---------------------------------------------------------------------------
# summary command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock)
async def test_summary_all_time(mock_send, session):
    _add_transaction(session, phone_number="234222", amount=20000)
    _add_transaction(session, phone_number="234222", amount=30000)
    await send_all_time_summary("234222", session)
    reply = mock_send.call_args[0][1]
    assert "₦50,000.00" in reply
    assert "2 transactions" in reply


# ---------------------------------------------------------------------------
# undo command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock)
async def test_undo_removes_last_transaction(mock_send, session):
    tx = _add_transaction(session, phone_number="234333", item="eggs", amount=1500)
    await undo_last_transaction("234333", session)
    reply = mock_send.call_args[0][1]
    assert "eggs" in reply
    assert "Deleted" in reply


@pytest.mark.asyncio
@patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock)
async def test_undo_no_transactions(mock_send, session):
    await undo_last_transaction("234_undo_empty", session)
    reply = mock_send.call_args[0][1]
    assert "No transactions" in reply


# ---------------------------------------------------------------------------
# export command routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock)
@patch("app.api.webhook.parse_sale_message", return_value=None)
async def test_export_command_sends_link(mock_parse, mock_send, session, monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://testserver.com")
    await process_incoming_message("234444", "export", session)
    reply = mock_send.call_args[0][1]
    assert "https://testserver.com/export" in reply


# ---------------------------------------------------------------------------
# CSV export content
# ---------------------------------------------------------------------------

def test_csv_export_contains_all_fields(sample_transaction):
    csv_data = generate_transactions_csv([sample_transaction])
    assert "rice" in csv_data
    assert "Hilary" in csv_data
    assert "200000" in csv_data
    assert "2348012345678" in csv_data
