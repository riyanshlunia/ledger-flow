#!/bin/sh
set -e

echo 'Seeding database...'
python scripts/seed_data.py

echo 'Running reconciliation agent...'
python - <<'EOF'
import sys
sys.path.insert(0, '/app')
from app.db.session import SessionLocal
from app.agents.reconciliation_agent import ReconciliationAgent
from app.agents.forecast_agent import ForecastAgent
from app.agents.governance_agent import GovernanceAgent
from app.models.models import Scenario

db = SessionLocal()
print('Running reconciliation...')
ReconciliationAgent().run(db, 'ENTITY-US-001')
print('Running forecast...')
agent = ForecastAgent()
scenarios = db.query(Scenario).filter_by(is_active=True).all()
gov = GovernanceAgent()
for scn in scenarios:
    forecasts = agent.run(db, 'ENTITY-US-001', scenario=scn if scn.id != 'SCN-001' else None)
    [gov.evaluate_forecast(db, f) for f in forecasts]
    db.commit()
    if scn.id == 'SCN-001':
        break
db.close()
print('Agents done!')
EOF

echo 'Starting API server...'
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
