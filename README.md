# SDCS Ledger

SDCS Ledger is an AI-powered WhatsApp accounting bot designed specifically for small business owners and sales teams. Instead of manually filling out spreadsheets or clicking through accounting apps, you simply send a natural WhatsApp message detailing your sale. The AI securely processes it and syncs it across a Master Multi-Tenant Web Dashboard.

## Features

- **Conversational Accounting:** Send raw text or Pidgin English (e.g., *"I sold 2 bags of rice for 15k"*).
- **Multi-Tenant Architecture:** Fully isolated business spaces utilizing rigorous state machines.
- **Team Management:** Add branch staff cleanly.
- **Executive Web Dashboard:** A highly premium, localized dashboard to view revenue trends natively, run refunds, and aggregate global master views.
- **WhatsApp Ledger Commands:** Full NLP tracking through WhatsApp Business.

## Technology Stack

- **Backend:** Python 3.12, FastAPI
- **Database:** PostgreSQL (Render Production), SQLModel / SQLAlchemy
- **Integration:** Meta Cloud API (WhatsApp Business), OpenAI API (gpt-4o-mini)
- **Frontend (Dashboard):** Responsive Tailwind CSS UI, Vanilla JS
- **Deployment:** Render Platform (Web Servce + PostgreSQL) / Docker

## Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Onikola-Waliyu/SDCS.git
   cd SDCS
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
