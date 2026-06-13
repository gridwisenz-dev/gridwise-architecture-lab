from __future__ import annotations

import csv
import html
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from gridwise_optimizer.models import (  # noqa: E402
    ForecastPoint,
    OptimizeRequest,
    PumpDecision,
    PumpOutagePoint,
    PumpState,
    TariffPoint,
    WellConfig,
    WellState,
)
from gridwise_optimizer.optimizer import _candidate_decisions, optimize  # noqa: E402
from gridwise_optimizer.simulator import SimulationError, simulate_tick  # noqa: E402
from scripts.generate_30_day_simulation import (  # noqa: E402
    INPUT_CSV,
    START,
    unavailable_pumps,
    write_csv,
)


RANDOM_SEED = 20260614
EXECUTION_TICKS = 24
FORECAST_TICKS = 96

ACTUAL_SIMULATION_CSV = ROOT / "data" / "actual_random_simulator_30_day.csv"
FORECAST_OPTIMIZER_CSV = ROOT / "data" / "optimizer_2_day_forecast_12_hour.csv"
COMPARISON_CSV = ROOT / "data" / "actual_vs_2_day_forecast_optimizer.csv"
COMPARISON_HTML = ROOT / "reports" / "actual_vs_2_day_forecast_optimizer.html"


def main() -> None:
    actual_rows = read_csv(INPUT_CSV)
    if not actual_rows:
        raise SystemExit("Run scripts/generate_30_day_simulation.py first.")

    rng = random.Random(RANDOM_SEED)
    forecast_rows = add_expected_inflows(actual_rows, rng)
    actual_simulation_rows = run_random_actual_simulator(forecast_rows, rng)
    optimizer_rows = run_12_hour_optimizer_with_2_day_forecast(forecast_rows)
    comparison_rows = build_comparison_rows(actual_simulation_rows, optimizer_rows)

    write_csv(ACTUAL_SIMULATION_CSV, actual_simulation_rows)
    write_csv(FORECAST_OPTIMIZER_CSV, optimizer_rows)
    write_csv(COMPARISON_CSV, comparison_rows)
    write_html_report(actual_simulation_rows, optimizer_rows, comparison_rows)

    print(f"wrote {ACTUAL_SIMULATION_CSV}")
    print(f"wrote {FORECAST_OPTIMIZER_CSV}")
    print(f"wrote {COMPARISON_CSV}")
    print(f"wrote {COMPARISON_HTML}")


def add_expected_inflows(rows: list[dict[str, str]], rng: random.Random) -> list[dict[str, str]]:
    result = []
    for row in rows:
        actual = float(row["inflow"])
        factor = 1 + rng.uniform(0, 0.10)
        result.append({**row, "expected_inflow": f"{actual * factor:.4f}"})
    return result


def run_random_actual_simulator(
    rows: list[dict[str, str]],
    rng: random.Random,
) -> list[dict[str, str]]:
    config = build_config()
    state = initial_state()
    output = []

    for row in rows:
        decisions = choose_random_feasible_decisions(config, state, row, rng)
        if decisions is None:
            output.append(failed_row(row, state.volume, "no feasible random simulator decision"))
            break

        try:
            simulated = simulate_tick(
                config,
                state,
                decisions,
                inflow=float(row["inflow"]),
                next_time=row["interval_end"],
            )
        except SimulationError as exc:
            output.append(failed_row(row, state.volume, str(exc)))
            break

        decision_by_pump = {decision.pump_id: decision for decision in decisions}
        output.append(
            {
                **row,
                "feasible": "true",
                "starting_volume": f"{state.volume:.2f}",
                "ending_volume": f"{simulated.ending_volume:.2f}",
                "p1_status": decision_by_pump["p1"].status,
                "p1_rate": f"{decision_by_pump['p1'].rate:.2f}",
                "p2_status": decision_by_pump["p2"].status,
                "p2_rate": f"{decision_by_pump['p2'].rate:.2f}",
                "pumped_volume": f"{simulated.pumped_volume:.2f}",
                "energy_cost": f"{simulated.pumped_volume * float(row['tariff']):.2f}",
                "warnings": "; ".join(simulated.warnings),
            }
        )
        state = simulated.state

    return output


def choose_random_feasible_decisions(
    config: WellConfig,
    state: WellState,
    row: dict[str, str],
    rng: random.Random,
) -> list[PumpDecision] | None:
    request = OptimizeRequest(
        config=config,
        state=state,
        inflow_forecast=[ForecastPoint(time=row["interval_end"], value=float(row["inflow"]))],
        tariff_forecast=[TariffPoint(time=row["interval_end"], cost_per_kwh=float(row["tariff"]))],
        pump_outage_forecast=[
            PumpOutagePoint(time=row["interval_end"], unavailable_pump_ids=unavailable_pumps(row))
        ],
        horizon_ticks=1,
    )
    candidates = list(_candidate_decisions(request, state, set(unavailable_pumps(row))))
    rng.shuffle(candidates)

    operating_band = []
    capacity_safe = []
    for decisions in candidates:
        try:
            simulated = simulate_tick(
                config,
                state,
                decisions,
                inflow=float(row["inflow"]),
                next_time=row["interval_end"],
            )
        except SimulationError:
            continue

        if config.low_water_mark <= simulated.ending_volume <= config.high_water_mark:
            operating_band.append(decisions)
        else:
            capacity_safe.append(decisions)

    if operating_band:
        return rng.choice(operating_band)
    if capacity_safe:
        return rng.choice(capacity_safe)
    return None


def run_12_hour_optimizer_with_2_day_forecast(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    config = build_config()
    state = initial_state()
    output = []

    for block_start in range(0, len(rows), EXECUTION_TICKS):
        forecast_rows = rows[block_start : block_start + FORECAST_TICKS]
        execution_rows = rows[block_start : block_start + EXECUTION_TICKS]
        if not execution_rows:
            break

        request = OptimizeRequest(
            config=config,
            state=state,
            inflow_forecast=[
                ForecastPoint(time=row["interval_end"], value=float(row["expected_inflow"]))
                for row in forecast_rows
            ],
            tariff_forecast=[
                TariffPoint(time=row["interval_end"], cost_per_kwh=float(row["tariff"]))
                for row in forecast_rows
            ],
            pump_outage_forecast=[
                PumpOutagePoint(time=row["interval_end"], unavailable_pump_ids=unavailable_pumps(row))
                for row in forecast_rows
            ],
            horizon_ticks=len(forecast_rows),
            tick_minutes=30,
            max_search_states=15,
        )
        response = optimize(request)

        if not response.feasible or len(response.plan) < len(execution_rows):
            for row in execution_rows:
                output.append(failed_row(row, state.volume, "; ".join(response.warnings)))
            break

        for row, step in zip(execution_rows, response.plan):
            try:
                simulated = simulate_tick(
                    config,
                    state,
                    step.decisions,
                    inflow=float(row["inflow"]),
                    next_time=row["interval_end"],
                )
            except SimulationError as exc:
                output.append(failed_row(row, state.volume, f"actual execution failed: {exc}"))
                break

            decision_by_pump = {decision.pump_id: decision for decision in step.decisions}
            output.append(
                {
                    **row,
                    "feasible": "true",
                    "starting_volume": f"{state.volume:.2f}",
                    "ending_volume": f"{simulated.ending_volume:.2f}",
                    "p1_status": decision_by_pump["p1"].status,
                    "p1_rate": f"{decision_by_pump['p1'].rate:.2f}",
                    "p2_status": decision_by_pump["p2"].status,
                    "p2_rate": f"{decision_by_pump['p2'].rate:.2f}",
                    "pumped_volume": f"{simulated.pumped_volume:.2f}",
                    "energy_cost": f"{simulated.pumped_volume * float(row['tariff']):.2f}",
                    "warnings": "; ".join(simulated.warnings),
                }
            )
            state = simulated.state
        else:
            continue

        break

    return output


def build_comparison_rows(
    actual_rows: list[dict[str, str]],
    optimizer_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows = []
    for actual, optimized in zip(actual_rows, optimizer_rows):
        actual_cost = float(actual["energy_cost"] or 0)
        optimized_cost = float(optimized["energy_cost"] or 0)
        rows.append(
            {
                "tick": actual["tick"],
                "timestamp": actual["timestamp"],
                "weather_pattern": actual["weather_pattern"],
                "tariff": actual["tariff"],
                "actual_inflow": actual["inflow"],
                "expected_inflow": actual["expected_inflow"],
                "random_simulator_cost": f"{actual_cost:.2f}",
                "forecast_optimizer_cost": f"{optimized_cost:.2f}",
                "cost_delta_optimizer_minus_random": f"{optimized_cost - actual_cost:.2f}",
                "random_simulator_ending_volume": actual["ending_volume"],
                "forecast_optimizer_ending_volume": optimized["ending_volume"],
                "random_simulator_pumped": actual["pumped_volume"],
                "forecast_optimizer_pumped": optimized["pumped_volume"],
                "random_simulator_warnings": actual["warnings"],
                "forecast_optimizer_warnings": optimized["warnings"],
            }
        )
    return rows


def build_config() -> WellConfig:
    return WellConfig(
        capacity=320,
        low_water_mark=45,
        high_water_mark=235,
        status_lookback_ticks=24,
        max_status_changes_in_lookback=6,
        pumps=[
            {"id": "p1", "allowed_rates": [0, 4, 8, 12, 16]},
            {"id": "p2", "allowed_rates": [0, 4, 8, 12, 16]},
        ],
    )


def initial_state() -> WellState:
    return WellState(
        time=START.isoformat(),
        volume=135,
        pumps=[
            PumpState(id="p1", status="Online", rate=0, recent_status_changes=["NoChange"] * 24),
            PumpState(id="p2", status="Online", rate=0, recent_status_changes=["NoChange"] * 24),
        ],
    )


def failed_row(row: dict[str, str], starting_volume: float, warning: str) -> dict[str, str]:
    return {
        **row,
        "feasible": "false",
        "starting_volume": f"{starting_volume:.2f}",
        "ending_volume": "",
        "p1_status": "",
        "p1_rate": "",
        "p2_status": "",
        "p2_rate": "",
        "pumped_volume": "",
        "energy_cost": "",
        "warnings": warning,
    }


def write_html_report(
    actual_rows: list[dict[str, str]],
    optimizer_rows: list[dict[str, str]],
    comparison_rows: list[dict[str, str]],
) -> None:
    actual = summarize(actual_rows)
    optimized = summarize(optimizer_rows)
    delta = optimized["cost"] - actual["cost"]
    percent = (delta / actual["cost"]) * 100 if actual["cost"] else 0

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Actual Simulator vs 2-Day Forecast Optimizer</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f7f9fb; color: #17202a; }}
    header {{ padding: 24px 32px; background: #fff; border-bottom: 1px solid #d9e2ec; }}
    main {{ padding: 24px 32px; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .metric {{ background: #fff; border: 1px solid #d9e2ec; border-radius: 6px; padding: 12px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 20px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e2ec; font-size: 12px; }}
    th, td {{ padding: 7px 8px; border-bottom: 1px solid #e7edf3; text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child, th:nth-child(3), td:nth-child(3) {{ text-align: left; }}
    th {{ background: #edf3f8; position: sticky; top: 0; }}
    .table-wrap {{ max-height: 620px; overflow: auto; }}
  </style>
</head>
<body>
  <header>
    <h1>Actual Simulator vs 2-Day Forecast Optimizer</h1>
    <div>Actual simulator uses randomized feasible actions. Optimizer receives 2 days of tariff and expected inflow data, then executes 12 hours before re-optimizing.</div>
  </header>
  <main>
    <div class="metrics">
      {metric("Random actual cost", f"{actual['cost']:,.2f}")}
      {metric("Forecast optimizer cost", f"{optimized['cost']:,.2f}")}
      {metric("Savings", f"{actual['cost'] - optimized['cost']:,.2f}")}
      {metric("Savings %", f"{-percent:.2f}%")}
    </div>

    <table>
      <thead>
        <tr><th>Measure</th><th>Random Actual Simulator</th><th>2-Day Forecast Optimizer</th></tr>
      </thead>
      <tbody>
        <tr><td>Total cost</td><td>{actual['cost']:.2f}</td><td>{optimized['cost']:.2f}</td></tr>
        <tr><td>Total pumped</td><td>{actual['pumped']:.2f}</td><td>{optimized['pumped']:.2f}</td></tr>
        <tr><td>Min volume</td><td>{actual['min_volume']:.2f}</td><td>{optimized['min_volume']:.2f}</td></tr>
        <tr><td>Max volume</td><td>{actual['max_volume']:.2f}</td><td>{optimized['max_volume']:.2f}</td></tr>
        <tr><td>Warnings</td><td>{actual['warnings']}</td><td>{optimized['warnings']}</td></tr>
        <tr><td>Infeasible rows</td><td>{actual['infeasible']}</td><td>{optimized['infeasible']}</td></tr>
      </tbody>
    </table>

    <h2>Interval Comparison</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th><th>Tariff</th><th>Pattern</th><th>Actual Inflow</th><th>Expected Inflow</th>
            <th>Random Cost</th><th>Optimizer Cost</th><th>Delta</th>
            <th>Random Vol</th><th>Optimizer Vol</th>
          </tr>
        </thead>
        <tbody>{''.join(comparison_row(row) for row in comparison_rows)}</tbody>
      </table>
    </div>
  </main>
</body>
</html>
"""
    COMPARISON_HTML.write_text(html_text)


def summarize(rows: list[dict[str, str]]) -> dict[str, float]:
    volumes = [float(row["ending_volume"]) for row in rows if row["ending_volume"]]
    return {
        "cost": sum(float(row["energy_cost"] or 0) for row in rows),
        "pumped": sum(float(row["pumped_volume"] or 0) for row in rows),
        "min_volume": min(volumes),
        "max_volume": max(volumes),
        "warnings": sum(1 for row in rows if row["warnings"]),
        "infeasible": sum(1 for row in rows if row["feasible"] != "true"),
    }


def metric(label: str, value: object) -> str:
    return f"<div class=\"metric\">{html.escape(label)}<strong>{html.escape(str(value))}</strong></div>"


def comparison_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row['timestamp'])}</td>"
        f"<td>{html.escape(row['tariff'])}</td>"
        f"<td>{html.escape(row['weather_pattern'])}</td>"
        f"<td>{html.escape(row['actual_inflow'])}</td>"
        f"<td>{html.escape(row['expected_inflow'])}</td>"
        f"<td>{html.escape(row['random_simulator_cost'])}</td>"
        f"<td>{html.escape(row['forecast_optimizer_cost'])}</td>"
        f"<td>{html.escape(row['cost_delta_optimizer_minus_random'])}</td>"
        f"<td>{html.escape(row['random_simulator_ending_volume'])}</td>"
        f"<td>{html.escape(row['forecast_optimizer_ending_volume'])}</td>"
        "</tr>"
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as file:
        return list(csv.DictReader(file))


if __name__ == "__main__":
    main()
