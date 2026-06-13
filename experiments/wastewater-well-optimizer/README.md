# Gridwise Optimizer

This project contains the wastewater well optimizer service.

The optimizer receives the current well model, current state, inflow forecast, and electricity tariff forecast. It returns a 12-hour operating plan at 30-minute intervals.

## Scope

- 30-minute clock ticks
- 12-hour optimization horizon by default
- 24 optimizer decisions per call
- Pump on/off and rate decisions
- Well-volume constraint checks
- Electricity-cost-aware scoring
- API endpoint ready to publish for external callers

## Local Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn gridwise_optimizer.api:app --reload
```

Then call:

```text
POST http://127.0.0.1:8000/optimize
GET  http://127.0.0.1:8000/health
```

## Test

```bash
python -m unittest discover -s tests
```

## Generate 30-Day Scenario View

```bash
python scripts/generate_30_day_simulation.py
```

This writes:

- `data/optimizer_30_day_input.csv`
- `data/optimizer_30_day_simulation.csv`
- `reports/optimizer_30_day_view.html`

## Compare 30-Minute And 12-Hour Cadence

```bash
python scripts/compare_12_hour_optimizer.py
```

This writes:

- `data/optimizer_12_hour_simulation.csv`
- `data/optimizer_12_hour_comparison.csv`
- `reports/optimizer_12_hour_comparison.html`

## Compare Actual Simulator And 2-Day Forecast Optimizer

```bash
python scripts/compare_actuals_vs_2_day_forecast_optimizer.py
```

This writes:

- `data/actual_random_simulator_30_day.csv`
- `data/optimizer_2_day_forecast_12_hour.csv`
- `data/actual_vs_2_day_forecast_optimizer.csv`
- `reports/actual_vs_2_day_forecast_optimizer.html`
