# Ghost Ledger 👻

Ghost Ledger is an AI-powered WhatsApp accounting bot designed specifically for small business owners and sales teams. Instead of manually filling out spreadsheets or clicking through accounting apps, you simply send a natural WhatsApp message detailing your sale. Ghost Ledger parses the message using OpenAI, automatically structures the data, calculates totals, and securely syncs it to a Multi-Tenant Web Dashboard.

## Features

- **Conversational Accounting:** Send raw text or Pidgin English (e.g., *"I sold 2 bags of rice for 15k"*). The AI automatically extracts the item, quantity, unit, price, and customer name.
- **Multi-Tenant Architecture:** Business owners can register their business directly from WhatsApp.
- **Team Management:** Owners can add staff members via WhatsApp or the Web UI. Staff can immediately start logging sales, and those sales funnel directly into the owner's unified dashboard.
- **Executive Web Dashboard:** A beautiful, responsive glassmorphic dashboard to view revenue trends, filter data by date, and export CSVs.
- **WhatsApp Ledger Commands:** Type `today`, `summary`, or `undo` right in the chat to manage your ledger on the go.

## Technology Stack

- **Backend:** Python 3.10+, FastAPI
- **Database:** PostgreSQL (or SQLite for local config), SQLModel / SQLAlchemy
- **Integration:** Meta Cloud API (WhatsApp Business), OpenAI API (gpt-4o-mini)
- **Frontend (Dashboard):** Jinja2 Templates, Vanilla JS, Custom CSS (Glassmorphism)
- **Deployment:** Docker & Docker Compose

## Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/iamproms/ghost-ledger.git
   cd ghost-ledger
   ```

2. **Set up Environment Variables:**
   Copy the example environment file and fill in your keys:
   ```bash
   cp .env.template .env
   ```
   *Required keys: `OPENAI_API_KEY`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`.*

3. **Start the Database (Docker):**
   ```bash
   docker-compose up -d db
   ```

4. **Run the Backend (Uvicorn):**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Expose to the Web (Ngrok):**
   ```bash
   ngrok http 8000
   ```
   *Copy your new Ngrok HTTPS URL and set it as your Meta Webhook URL (append `/webhook`).*

## License
MIT License
