from __future__ import annotations

import csv
import html
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from gridwise_optimizer.models import (  # noqa: E402
    ForecastPoint,
    OptimizeRequest,
    PumpOutagePoint,
    PumpState,
    TariffPoint,
    WellConfig,
    WellState,
)
from gridwise_optimizer.optimizer import optimize  # noqa: E402
from scripts.generate_30_day_simulation import (  # noqa: E402
    HORIZON_TICKS,
    INPUT_CSV,
    OUTPUT_CSV,
    START,
    unavailable_pumps,
    write_csv,
)


COMPARISON_CSV = ROOT / "data" / "optimizer_12_hour_comparison.csv"
COMPARISON_HTML = ROOT / "reports" / "optimizer_12_hour_comparison.html"
TWELVE_HOUR_OUTPUT_CSV = ROOT / "data" / "optimizer_12_hour_simulation.csv"


def main() -> None:
    input_rows = read_csv(INPUT_CSV)
    if not input_rows:
        raise SystemExit(f"missing input rows: run scripts/generate_30_day_simulation.py first")

    thirty_min_rows = read_csv(OUTPUT_CSV)
    if not thirty_min_rows:
        raise SystemExit(f"missing 30-minute simulation: run scripts/generate_30_day_simulation.py first")

    twelve_hour_rows = run_12_hour_cadence(input_rows)
    comparison_rows = build_comparison_rows(thirty_min_rows, twelve_hour_rows)

    write_csv(TWELVE_HOUR_OUTPUT_CSV, twelve_hour_rows)
    write_csv(COMPARISON_CSV, comparison_rows)
    write_html_report(thirty_min_rows, twelve_hour_rows, comparison_rows)

    print(f"wrote {TWELVE_HOUR_OUTPUT_CSV}")
    print(f"wrote {COMPARISON_CSV}")
    print(f"wrote {COMPARISON_HTML}")


def run_12_hour_cadence(input_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    config = build_config()
    state = initial_state()
    output_rows: list[dict[str, str]] = []

    for chunk_start in range(0, len(input_rows), HORIZON_TICKS):
        horizon_rows = input_rows[chunk_start : chunk_start + HORIZON_TICKS]
        request = OptimizeRequest(
            config=config,
            state=state,
            inflow_forecast=[
                ForecastPoint(time=item["interval_end"], value=float(item["inflow"]))
                for item in horizon_rows
            ],
            tariff_forecast=[
                TariffPoint(time=item["interval_end"], cost_per_kwh=float(item["tariff"]))
                for item in horizon_rows
            ],
            pump_outage_forecast=[
                PumpOutagePoint(time=item["interval_end"], unavailable_pump_ids=unavailable_pumps(item))
                for item in horizon_rows
            ],
            horizon_ticks=len(horizon_rows),
            tick_minutes=30,
        )
        response = optimize(request)

        if not response.feasible or len(response.plan) != len(horizon_rows):
            for row in horizon_rows:
                output_rows.append(
                    {
                        **row,
                        "feasible": "false",
                        "starting_volume": f"{state.volume:.2f}",
                        "ending_volume": "",
                        "p1_status": "",
                        "p1_rate": "",
                        "p2_status": "",
                        "p2_rate": "",
                        "pumped_volume": "",
                        "energy_cost": "",
                        "warnings": "; ".join(response.warnings),
                    }
                )
            break

        for row, step in zip(horizon_rows, response.plan):
            decision_by_pump = {decision.pump_id: decision for decision in step.decisions}
            output_rows.append(
                {
                    **row,
                    "feasible": "true",
                    "starting_volume": f"{step.starting_volume:.2f}",
                    "ending_volume": f"{step.ending_volume:.2f}",
                    "p1_status": decision_by_pump["p1"].status,
                    "p1_rate": f"{decision_by_pump['p1'].rate:.2f}",
                    "p2_status": decision_by_pump["p2"].status,
                    "p2_rate": f"{decision_by_pump['p2'].rate:.2f}",
                    "pumped_volume": f"{step.pumped_volume:.2f}",
                    "energy_cost": f"{step.energy_cost:.2f}",
                    "warnings": "; ".join(step.warnings),
                }
            )
            state = response_state_from_step(state, step)

    return output_rows


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


def response_state_from_step(previous_state: WellState, step) -> WellState:
    previous_by_id = {pump.id: pump for pump in previous_state.pumps}
    next_pumps = []
    for decision in step.decisions:
        previous = previous_by_id[decision.pump_id]
        recent = [decision.change_status, *previous.recent_status_changes][:24]
        next_pumps.append(
            previous.model_copy(
                update={
                    "status": decision.status,
                    "rate": decision.rate,
                    "recent_status_changes": recent,
                }
            )
        )
    return WellState(time=step.time, volume=step.ending_volume, pumps=next_pumps)


def build_comparison_rows(
    thirty_min_rows: list[dict[str, str]],
    twelve_hour_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows = []
    for simulation, optimization in zip(thirty_min_rows, twelve_hour_rows):
        sim_cost = float(simulation["energy_cost"] or 0)
        opt_cost = float(optimization["energy_cost"] or 0)
        rows.append(
            {
                "tick": simulation["tick"],
                "timestamp": simulation["timestamp"],
                "weather_pattern": simulation["weather_pattern"],
                "tariff": simulation["tariff"],
                "inflow": simulation["inflow"],
                "simulation_30_min_cost": f"{sim_cost:.2f}",
                "optimizer_12_hour_cost": f"{opt_cost:.2f}",
                "cost_delta_12h_minus_30m": f"{opt_cost - sim_cost:.2f}",
                "simulation_30_min_ending_volume": simulation["ending_volume"],
                "optimizer_12_hour_ending_volume": optimization["ending_volume"],
                "simulation_30_min_pumped": simulation["pumped_volume"],
                "optimizer_12_hour_pumped": optimization["pumped_volume"],
                "simulation_30_min_warnings": simulation["warnings"],
                "optimizer_12_hour_warnings": optimization["warnings"],
            }
        )
    return rows


def write_html_report(
    thirty_min_rows: list[dict[str, str]],
    twelve_hour_rows: list[dict[str, str]],
    comparison_rows: list[dict[str, str]],
) -> None:
    sim = summarize(thirty_min_rows)
    opt = summarize(twelve_hour_rows)
    delta = opt["cost"] - sim["cost"]
    percent = (delta / sim["cost"]) * 100 if sim["cost"] else 0

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>30-Minute vs 12-Hour Optimizer Cadence</title>
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
    <h1>30-Minute Receding Simulation vs 12-Hour Optimizer Cadence</h1>
    <div>Same 30-day input data, tariffs, pump outage periods, and well constraints.</div>
  </header>
  <main>
    <div class="metrics">
      {metric("30-minute total cost", f"{sim['cost']:,.2f}")}
      {metric("12-hour total cost", f"{opt['cost']:,.2f}")}
      {metric("Delta", f"{delta:,.2f}")}
      {metric("Delta %", f"{percent:.2f}%")}
    </div>

    <table>
      <thead>
        <tr><th>Measure</th><th>30-Minute Receding</th><th>12-Hour Cadence</th></tr>
      </thead>
      <tbody>
        <tr><td>Total pumped</td><td>{sim['pumped']:.2f}</td><td>{opt['pumped']:.2f}</td></tr>
        <tr><td>Min volume</td><td>{sim['min_volume']:.2f}</td><td>{opt['min_volume']:.2f}</td></tr>
        <tr><td>Max volume</td><td>{sim['max_volume']:.2f}</td><td>{opt['max_volume']:.2f}</td></tr>
        <tr><td>Warning rows</td><td>{sim['warnings']}</td><td>{opt['warnings']}</td></tr>
        <tr><td>Infeasible rows</td><td>{sim['infeasible']}</td><td>{opt['infeasible']}</td></tr>
      </tbody>
    </table>

    <h2>Interval Comparison</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th><th>Tariff</th><th>Pattern</th><th>Inflow</th>
            <th>30m Cost</th><th>12h Cost</th><th>Delta</th>
            <th>30m Volume</th><th>12h Volume</th>
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
        f"<td>{html.escape(row['inflow'])}</td>"
        f"<td>{html.escape(row['simulation_30_min_cost'])}</td>"
        f"<td>{html.escape(row['optimizer_12_hour_cost'])}</td>"
        f"<td>{html.escape(row['cost_delta_12h_minus_30m'])}</td>"
        f"<td>{html.escape(row['simulation_30_min_ending_volume'])}</td>"
        f"<td>{html.escape(row['optimizer_12_hour_ending_volume'])}</td>"
        "</tr>"
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as file:
        return list(csv.DictReader(file))


if __name__ == "__main__":
    main()

