import hashlib
import hmac
import logging
import os
from contextlib import contextmanager
from typing import Optional, cast

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.responses import Response
from sqlmodel import Session, select

from app.db.models import Business, Transaction, User, UserRole, UserState, engine, get_session
from app.services.parser import parse_sale_message
from app.services.whatsapp import send_whatsapp_message
from app.utils.exporter import generate_transactions_csv
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: Optional[str]) -> bool:
    """Validate X-Hub-Signature-256 from Meta to prevent forged requests."""
    if not APP_SECRET:
        logger.warning("WHATSAPP_APP_SECRET not set — skipping signature verification.")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, cast(str, signature_header))


@contextmanager
def safe_session(session: Optional[Session] = None):
    if session:
        yield session
    else:
        with Session(engine) as s:
            yield s


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Meta webhook verification challenge."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("Webhook verification failed — token mismatch or wrong mode.")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None, alias="x-hub-signature-256"),
):
    """Receive and process incoming WhatsApp messages."""
    body = await request.body()

    if not _verify_signature(body, x_hub_signature_256):
        logger.error("Invalid webhook signature — request rejected.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = await request.json()
        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for message in value.get("messages", []):
                        phone_number = message["from"]
                        text = message.get("text", {}).get("body", "")
                        if text:
                            background_tasks.add_task(process_incoming_message, phone_number, text)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Webhook processing error: %s", e)
        return {"status": "error", "message": str(e)}



# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def process_incoming_message(phone_number: str, text: str, session: Optional[Session] = None):
    import bcrypt
    clean_text = text.lower().strip()

    with safe_session(session) as db:
        user = db.get(User, phone_number)

        # ── NEW USER: No record at all ─────────────────────────────────────
        if user is None:
            new_user = User(
                phone_number=phone_number,
                state=UserState.AWAITING_BUSINESS_NAME,
                role=UserRole.OWNER,
            )
            db.add(new_user)
            db.commit()
            reply = (
                "👋 Welcome to SDCS Ledger!\n\n"
                "I'll help you track your sales automatically via WhatsApp.\n\n"
                "To get started, please reply with your *Business Name*:"
            )
            await send_whatsapp_message(phone_number, reply)
            return

        # ── AWAITING BUSINESS NAME: Owner setting up ───────────────────────
        if user.state == UserState.AWAITING_BUSINESS_NAME:
            business_name = text.strip()
            business = Business(name=business_name)
            db.add(business)
            db.commit()
            db.refresh(business)
            user.business_id = business.id
            user.state = UserState.ACTIVE
            user.name = business_name  # temporary display name — owner = business
            db.add(user)
            db.commit()
            reply = (
                f"✅ *{business_name}* is all set up!\n\n"
                "You can now start recording your sales. Just send me something like:\n"
                "_\"Sold 2 bags of rice for 10k\"_\n\n"
                "Other commands:\n"
                "• *today* — today's summary\n"
                "• *summary* — all‑time summary\n"
                "• *undo* — remove last entry\n"
                "• *add staff 2348012345678* — add a team member\n"
                "• *pin 1234* — set PIN for dashboard access"
            )
            await send_whatsapp_message(phone_number, reply)
            return

        # ── ACTIVE USER commands ───────────────────────────────────────────
        if clean_text == "today":
            await send_daily_summary(phone_number, user, db)
            return

        if clean_text == "summary":
            await send_all_time_summary(phone_number, user, db)
            return

        if clean_text == "undo":
            await undo_last_transaction(phone_number, user, db)
            return

        if clean_text == "export":
            base_url = os.getenv("BASE_URL", "https://your-app-url.com")
            reply = f"📊 Download your transaction report here: {base_url}/export"
            await send_whatsapp_message(phone_number, reply)
            return

        # Handle PIN setup: "pin 1234"
        if clean_text.startswith("pin "):
            if user.role != UserRole.OWNER:
                await send_whatsapp_message(phone_number, "⚠️ Only the business owner can set a dashboard PIN.")
                return
            parts = text.strip().split()
            if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
                raw_pin = parts[1]
                user.pin_hash = bcrypt.hashpw(raw_pin.encode(), bcrypt.gensalt()).decode()
                db.add(user)
                db.commit()
                base_url = os.getenv("BASE_URL", "http://localhost:8000")
                reply = (
                    f"🔐 PIN set successfully! Access your business dashboard here:\n"
                    f"{base_url}/my-ledger"
                )
            else:
                reply = "⚠️ Invalid format. Use: *pin 1234* (exactly 4 digits)"
            await send_whatsapp_message(phone_number, reply)
            return

        # Handle "add staff <phone>" command (owners only)
        if clean_text.startswith("add staff "):
            await handle_add_staff(phone_number, user, clean_text, db)
            return

        # ── SALE RECORDING ─────────────────────────────────────────────────
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        success_count = 0
        total_added = 0.0
        reply_lines = []
        
        for line in lines:
            parsed_data = parse_sale_message(line)
            if not parsed_data:
                reply_lines.append(f"❌ '{line[:15]}...' (Invalid format)")
                continue
                
            transaction = Transaction(
                business_id=user.business_id,
                recorded_by=phone_number,
                item=parsed_data["item"],
                quantity=parsed_data["quantity"],
                unit=parsed_data["unit"],
                amount=parsed_data["amount"],
                customer=parsed_data.get("customer"),
                status="recorded"
            )
            db.add(transaction)
            success_count += 1
            total_added += parsed_data["amount"]
            
            q = float(transaction.quantity)
            qty_str = f"{int(q)}" if q.is_integer() else f"{q}"
            
            rec_str = f"✅ Recorded: {qty_str} {transaction.unit} of {transaction.item} – ₦{transaction.amount:,.2f}"
            if transaction.customer:
                rec_str += f" (Customer: {transaction.customer})"
            reply_lines.append(rec_str)
            
        db.commit()
        
        if success_count > 0:
            header = f"🚀 Successfully processed {success_count} item(s):\n\n"
            footer = f"\n\n💰 Total Added: ₦{total_added:,.2f}\nType 'today' or 'summary' to check metrics."
            final_msg = header + "\n".join(reply_lines) + footer
            await send_whatsapp_message(phone_number, final_msg)
        else:
            await send_whatsapp_message(
                phone_number,
                "❌ Couldn't parse any sales.\n\nFormat each line like:\n*5 Rice 3000 Cash*\n\n(Qty | Item | Total Amount | Payment Method)"
            )

# ---------------------------------------------------------------------------
# Staff management
# ---------------------------------------------------------------------------

async def handle_add_staff(owner_phone: str, owner: User, clean_text: str, db: Session):
    if owner.role != UserRole.OWNER:
        await send_whatsapp_message(owner_phone, "⚠️ Only the business owner can add staff members.")
        return

    parts = clean_text.split()
    if len(parts) < 3:
        await send_whatsapp_message(owner_phone, "⚠️ Format: *add staff 2348012345678*")
        return

    staff_phone = parts[2].strip().replace("+", "").replace(" ", "").replace("-", "")
    if not staff_phone.isdigit():
        await send_whatsapp_message(owner_phone, "⚠️ Invalid phone number. Use digits only (e.g. *add staff 2348012345678*)")
        return

    existing = db.get(User, staff_phone)
    if existing:
        if existing.business_id == owner.business_id:
            await send_whatsapp_message(owner_phone, f"⚠️ {staff_phone} is already part of your team.")
        else:
            await send_whatsapp_message(owner_phone, f"⚠️ {staff_phone} is already registered with another business.")
        return

    # Create the staff user linked to the owner's business
    business = db.get(Business, owner.business_id)
    staff = User(
        phone_number=staff_phone,
        business_id=owner.business_id,
        role=UserRole.STAFF,
        state=UserState.ACTIVE,  # Staff skip onboarding
    )
    db.add(staff)
    db.commit()

    # Notify the owner
    await send_whatsapp_message(owner_phone, f"✅ {staff_phone} has been added to your team!")
    # Notify the new staff member
    business_name = business.name if business else "your business"
    await send_whatsapp_message(
        staff_phone,
        f"👋 You've been added as a sales agent for *{business_name}* on SDCS Ledger!\n\n"
        "You can start recording sales right away. Just send a message like:\n"
        "_\"Sold 3 bottles of oil for 6k\"_"
    )


# ---------------------------------------------------------------------------
# Summary helpers (scoped to business)
# ---------------------------------------------------------------------------

async def send_daily_summary(phone_number: str, user: User, db: Session):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    statement = select(Transaction).where(
        Transaction.business_id == user.business_id,
        Transaction.created_at >= today_start,
    )
    results = db.exec(statement).all()
    total_amount = sum(t.amount for t in results)
    count = len(results)
    label = "your business" if user.role == UserRole.OWNER else "your"
    reply = f"Today's sales for {label}: ₦{total_amount:,.2f} ({count} transaction{'s' if count != 1 else ''})"
    await send_whatsapp_message(phone_number, reply)


async def send_all_time_summary(phone_number: str, user: User, db: Session):
    statement = select(Transaction).where(Transaction.business_id == user.business_id)
    results = db.exec(statement).all()
    total_amount = sum(t.amount for t in results)
    count = len(results)
    reply = f"All‑time Summary: ₦{total_amount:,.2f} ({count} transaction{'s' if count != 1 else ''})"
    await send_whatsapp_message(phone_number, reply)


async def undo_last_transaction(phone_number: str, user: User, db: Session):
    # Undo the sender's own last entry (not the business-wide last)
    statement = (
        select(Transaction)
        .where(Transaction.recorded_by == phone_number)
        .order_by(Transaction.id.desc())
        .limit(1)
    )
    last_tx = db.exec(statement).first()
    if last_tx:
        db.delete(last_tx)
        db.commit()
        reply = f"🗑 Deleted last entry: {last_tx.item} (₦{last_tx.amount:,.2f})"
    else:
        reply = "No transactions found to undo."
    await send_whatsapp_message(phone_number, reply)
