# Gridwise Optimizer

This project contains the wastewater well optimizer service.

The optimizer receives the current well model, current state, inflow forecast, electricity tariff forecast, and pump outage forecast. It returns a 30-minute interval operating plan across the supplied forecast horizon.

For the current publication path, callers pass the next 2 days of forecast inputs and execute the first 12 hours of the returned plan before re-optimizing.

## Scope

- 30-minute clock ticks
- 30-minute interval optimization
- 2-day forecast input mode for the current comparison and publication path
- 12-hour execution cadence before re-optimizing
- 12-hour API default if no horizon is specified
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

## Configuration Reference

See `CONFIGURATION.md` for the optimizer request format, well configuration values, tariff file format, and scenario input file format.

## Deployment

See `DEPLOYMENT.md` for the target public endpoint and setup notes for `https://app.gridwise.nz/optimise`.

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

## Compare Actual And 2-Day Forecast Optimizer

```bash
python scripts/compare_actuals_vs_2_day_forecast_optimizer.py
```

This compares an actual randomized feasible simulator against the optimizer. The optimizer receives 2 days of tariff and expected inflow details, then executes the first 12 hours before re-optimizing.

This writes:

- `data/actual_30_day.csv`
- `data/optimizer_2_day_forecast_12_hour.csv`
- `data/actual_vs_2_day_forecast_optimizer.csv`
- `reports/actual_vs_2_day_forecast_optimizer.html`
