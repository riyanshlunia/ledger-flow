# LedgerFlow Agent

LedgerFlow is an intelligent, agent-driven platform designed to automate and streamline Accounts Receivable (AR) and Accounts Payable (AP) reconciliation, while providing comprehensive, AI-driven cash flow forecasting.

## Overview

Modern finance operations demand precision, predictability, and automation. LedgerFlow replaces manual, error-prone spreadsheet processes with a rolling 13-week forecast model. Utilizing robust predictive analytics and natural language generation, LedgerFlow offers finance teams full transparency and confidence in their cash position.

### Key Features

- **Automated Reconciliation**: Instantly reconcile incoming bank transactions with internal ERP records, reducing manual accounting hours.
- **Cash Flow Forecasting**: Generate a rolling 13-week cash flow forecast using probabilistic models based on historical customer payment behavior (AR) and scheduled vendor bills (AP).
- **Explainable AI**: Forecasts include natural-language summaries that transparently explain underlying models, identify key drivers, and highlight cash flow risks.
- **Scenario Analysis**: Run "what-if" stress tests by manipulating variables like Days Sales Outstanding (DSO) or foreign exchange rates to see immediate cash flow impacts.
- **Audit Trails**: Fully transparent HMAC-signed audit logging for compliance and review.

## Architecture

LedgerFlow is composed of two primary services:
- **Backend (Python)**: Houses the core business logic, the `ForecastAgent`, machine learning models, database models (SQLAlchemy), and RESTful APIs.
- **Frontend (Next.js)**: A polished, corporate-grade dashboard built on React for visualizing insights, tracking escalations, and reviewing forecasts.

## Getting Started

### Prerequisites
- Node.js (v18 or higher)
- Python (3.9 or higher)
- Docker & Docker Compose (optional, for containerized deployments)

### Local Development

1. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

2. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Running via Docker**
   Alternatively, you can spin up the entire stack using Docker Compose:
   ```bash
   docker-compose up --build
   ```

## Security & Compliance

LedgerFlow is built with strict corporate compliance in mind. All forecast and reconciliation decisions are logged via an immutable audit trail, ensuring that every automated action is traceable and justifiable.

## Free Hosting

The frontend is deployment-ready for Vercel and the FastAPI service can run on any Python host that supports a web service (for example, Render's free tier where available). The database should use a managed PostgreSQL provider rather than the local Docker volume.

1. Deploy `frontend/` as a Next.js project on Vercel and set `NEXT_PUBLIC_API_URL` to the deployed API URL ending in `/v1`.
2. Deploy `backend/` as a Python web service with the start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Set `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ENVIRONMENT=production`, and `CORS_ORIGINS` on the backend. Set `CORS_ORIGINS` to the exact Vercel origin, for example `https://ledgerflow-demo.vercel.app`.
4. Run `npm run build` from `frontend/` before publishing. The API health check is available at `/health` and interactive API documentation at `/docs`.

For local development, copy `frontend/.env.example` to `frontend/.env.local` and `backend/.env.example` to `backend/.env`.

---
