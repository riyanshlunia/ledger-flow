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

---
