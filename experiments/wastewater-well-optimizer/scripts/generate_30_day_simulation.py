from __future__ import annotations

import csv
import html
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from gridwise_optimizer.models import (
    ForecastPoint,
    OptimizeRequest,
    PumpOutagePoint,
    PumpState,
    TariffPoint,
    WellConfig,
    WellState,
)
from gridwise_optimizer.optimizer import optimize


DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
INPUT_CSV = DATA_DIR / "optimizer_30_day_input.csv"
OUTPUT_CSV = DATA_DIR / "optimizer_30_day_simulation.csv"
VIEW_HTML = REPORT_DIR / "optimizer_30_day_view.html"

SEED = 20260613
START = datetime(2026, 6, 1, tzinfo=timezone.utc)
DAYS = 30
TICKS_PER_DAY = 48
TOTAL_TICKS = DAYS * TICKS_PER_DAY
HORIZON_TICKS = 24

JUNE_TARIFFS = {
    "T1-T8": 228.42,
    "T9-T16": 257.37,
    "T17-T24": 282.66,
    "T25-T32": 283.90,
    "T33-T40": 302.47,
    "T41-T48": 277.06,
}

DAY_PATTERNS = [
    "dry",
    "dry",
    "wet",
    "wet",
    "severe_wet_afternoon",
    "extreme_dry",
    "wet",
    "dry_spell",
    "wet_multi_day",
    "wet_multi_day",
    "dry_spell",
    "wet_multi_day",
    "wet_multi_day",
    "extreme_wet",
    "dry",
    "extreme_dry",
    "wet",
    "severe_wet_afternoon",
    "wet_multi_day",
    "wet_multi_day",
    "wet_multi_day",
    "wet_multi_day",
    "dry_spell",
    "wet_multi_day",
    "dry",
    "extreme_wet",
    "wet",
    "dry",
    "severe_wet_afternoon",
    "extreme_dry",
]


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    rng = random.Random(SEED)
    outages = build_outages(rng)
    input_rows = build_input_rows(rng, outages)
    simulation_rows = run_simulation(input_rows)

    write_csv(INPUT_CSV, input_rows)
    write_csv(OUTPUT_CSV, simulation_rows)
    write_html_view(input_rows, simulation_rows)

    print(f"wrote {INPUT_CSV}")
    print(f"wrote {OUTPUT_CSV}")
    print(f"wrote {VIEW_HTML}")


def build_input_rows(rng: random.Random, outages: dict[int, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for tick in range(TOTAL_TICKS):
        current = START + timedelta(minutes=30 * tick)
        interval_end = current + timedelta(minutes=30)
        day_index = tick // TICKS_PER_DAY
        period = tick % TICKS_PER_DAY + 1
        pattern = DAY_PATTERNS[day_index]
        tariff_band = tariff_band_for_period(period)
        outage_pump = outages.get(tick, "")

        rows.append(
            {
                "tick": str(tick + 1),
                "timestamp": current.isoformat(),
                "interval_end": interval_end.isoformat(),
                "day": str(day_index + 1),
                "time_period": f"T{period}",
                "tariff_band": tariff_band,
                "tariff": f"{JUNE_TARIFFS[tariff_band]:.2f}",
                "weather_pattern": pattern,
                "inflow": f"{inflow_for_period(pattern, period, rng):.2f}",
                "p1_out_of_action": "true" if outage_pump == "p1" else "false",
                "p2_out_of_action": "true" if outage_pump == "p2" else "false",
            }
        )

    return rows


def build_outages(rng: random.Random) -> dict[int, str]:
    target_ticks = int(TOTAL_TICKS * 0.25)
    outages: dict[int, str] = {}
    attempts = 0

    while len(outages) < target_ticks and attempts < 10_000:
        attempts += 1
        block_length = rng.randint(4, 12)
        start = rng.randint(0, TOTAL_TICKS - block_length)
        block_ticks = range(start, start + block_length)

        if any(tick in outages for tick in block_ticks):
            continue

        pump_id = rng.choice(["p1", "p2"])
        for tick in block_ticks:
            if len(outages) >= target_ticks:
                break
            outages[tick] = pump_id

    return outages


def inflow_for_period(pattern: str, period: int, rng: random.Random) -> float:
    hour = (period - 1) / 2

    if 0 <= hour < 5.5:
        base = 0.55
    elif 5.5 <= hour < 10.5:
        base = 2.80
    elif 10.5 <= hour < 16:
        base = 1.35
    elif 16 <= hour < 21.5:
        base = 3.10
    else:
        base = 0.70

    noise = rng.uniform(-0.18, 0.18)

    if pattern == "extreme_dry":
        value = base * 0.22 + noise
    elif pattern == "dry_spell":
        value = base * 0.35 + noise
    elif pattern == "dry":
        value = base * 0.60 + noise
    elif pattern == "wet":
        value = 1.50 + base * 1.35 + rng.uniform(-0.25, 0.35)
    elif pattern == "wet_multi_day":
        value = 1.90 + base * 1.55 + rng.uniform(-0.20, 0.45)
    elif pattern == "severe_wet_afternoon":
        if 24 <= period <= 38:
            value = 6.20 + base * 1.95 + rng.uniform(-0.35, 0.55)
        else:
            value = 1.60 + base * 1.10 + rng.uniform(-0.20, 0.35)
    elif pattern == "extreme_wet":
        if 24 <= period <= 40:
            value = 7.30 + base * 2.10 + rng.uniform(-0.30, 0.65)
        else:
            value = 3.90 + base * 1.80 + rng.uniform(-0.25, 0.50)
    else:
        value = base + noise

    return max(0.05, value)


def tariff_band_for_period(period: int) -> str:
    if period <= 8:
        return "T1-T8"
    if period <= 16:
        return "T9-T16"
    if period <= 24:
        return "T17-T24"
    if period <= 32:
        return "T25-T32"
    if period <= 40:
        return "T33-T40"
    return "T41-T48"


def run_simulation(input_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    config = WellConfig(
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
    state = WellState(
        time=START.isoformat(),
        volume=135,
        pumps=[
            PumpState(id="p1", status="Online", rate=0, recent_status_changes=["NoChange"] * 24),
            PumpState(id="p2", status="Online", rate=0, recent_status_changes=["NoChange"] * 24),
        ],
    )

    simulation_rows: list[dict[str, str]] = []

    for index, row in enumerate(input_rows):
        horizon_rows = input_rows[index : index + HORIZON_TICKS]
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

        if not response.feasible or not response.plan:
            simulation_rows.append(
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

        step = response.plan[0]
        decision_by_pump = {decision.pump_id: decision for decision in step.decisions}
        simulation_rows.append(
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

    return simulation_rows


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


def unavailable_pumps(row: dict[str, str]) -> list[str]:
    pumps = []
    if row["p1_out_of_action"] == "true":
        pumps.append("p1")
    if row["p2_out_of_action"] == "true":
        pumps.append("p2")
    return pumps


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_html_view(input_rows: list[dict[str, str]], simulation_rows: list[dict[str, str]]) -> None:
    weather_counts = Counter(row["weather_pattern"] for row in input_rows)
    outage_ticks = sum(
        1
        for row in input_rows
        if row["p1_out_of_action"] == "true" or row["p2_out_of_action"] == "true"
    )
    total_cost = sum(float(row["energy_cost"] or 0) for row in simulation_rows)
    ending_volumes = [float(row["ending_volume"]) for row in simulation_rows if row["ending_volume"]]
    warnings = [row for row in simulation_rows if row["warnings"]]
    feasible = all(row["feasible"] == "true" for row in simulation_rows)
    day_summaries = summarize_by_day(simulation_rows)

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gridwise 30-Day Optimizer Simulation</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #17202a; background: #f7f9fb; }}
    header {{ padding: 24px 32px; background: #ffffff; border-bottom: 1px solid #d9e2ec; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    main {{ padding: 24px 32px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(5, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .metric {{ background: #fff; border: 1px solid #d9e2ec; border-radius: 6px; padding: 12px; }}
    .metric strong {{ display: block; font-size: 20px; margin-top: 6px; }}
    section {{ margin-bottom: 28px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e2ec; font-size: 12px; }}
    th, td {{ padding: 7px 8px; border-bottom: 1px solid #e7edf3; text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child, th:nth-child(4), td:nth-child(4) {{ text-align: left; }}
    th {{ position: sticky; top: 0; background: #edf3f8; z-index: 1; }}
    .table-wrap {{ max-height: 620px; overflow: auto; border: 1px solid #d9e2ec; }}
    .ok {{ color: #176b3a; }}
    .warn {{ color: #9a3412; }}
  </style>
</head>
<body>
  <header>
    <h1>Gridwise 30-Day Optimizer Simulation</h1>
    <div>30 days, 30-minute intervals, June tariff periods, mixed dry/wet weather, and one-pump outage periods.</div>
  </header>
  <main>
    <div class="metrics">
      {metric("Intervals", len(input_rows))}
      {metric("Feasible", "Yes" if feasible else "No")}
      {metric("Pump outage share", f"{outage_ticks / len(input_rows):.1%}")}
      {metric("Total energy cost", f"{total_cost:,.2f}")}
      {metric("Volume range", f"{min(ending_volumes):.1f} - {max(ending_volumes):.1f}" if ending_volumes else "n/a")}
    </div>

    <section>
      <h2>Weather Pattern Mix</h2>
      <table>
        <thead><tr><th>Pattern</th><th>Intervals</th><th>Days Equivalent</th></tr></thead>
        <tbody>
          {''.join(f"<tr><td>{html.escape(pattern)}</td><td>{count}</td><td>{count / TICKS_PER_DAY:.1f}</td></tr>" for pattern, count in weather_counts.items())}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Daily Summary</h2>
      <table>
        <thead><tr><th>Day</th><th>Pattern</th><th>Inflow</th><th>Pumped</th><th>Cost</th><th>Min Volume</th><th>Max Volume</th><th>Outage Ticks</th><th>Warnings</th></tr></thead>
        <tbody>{''.join(day_summary_row(row) for row in day_summaries)}</tbody>
      </table>
    </section>

    <section>
      <h2>Interval View</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Period</th><th>Tariff</th><th>Pattern</th><th>Inflow</th><th>Outage</th>
              <th>Start Vol</th><th>End Vol</th><th>P1</th><th>P1 Rate</th><th>P2</th><th>P2 Rate</th><th>Pumped</th><th>Cost</th><th>Warnings</th>
            </tr>
          </thead>
          <tbody>{''.join(interval_row(row) for row in simulation_rows)}</tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>
"""
    VIEW_HTML.write_text(html_text)


def summarize_by_day(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["day"]].append(row)

    summaries = []
    for day, day_rows in grouped.items():
        volumes = [float(row["ending_volume"]) for row in day_rows if row["ending_volume"]]
        summaries.append(
            {
                "day": int(day),
                "pattern": day_rows[0]["weather_pattern"],
                "inflow": sum(float(row["inflow"]) for row in day_rows),
                "pumped": sum(float(row["pumped_volume"] or 0) for row in day_rows),
                "cost": sum(float(row["energy_cost"] or 0) for row in day_rows),
                "min_volume": min(volumes) if volumes else 0,
                "max_volume": max(volumes) if volumes else 0,
                "outage_ticks": sum(
                    1
                    for row in day_rows
                    if row["p1_out_of_action"] == "true" or row["p2_out_of_action"] == "true"
                ),
                "warnings": sum(1 for row in day_rows if row["warnings"]),
            }
        )

    return sorted(summaries, key=lambda item: item["day"])


def metric(label: str, value: object) -> str:
    return f"<div class=\"metric\">{html.escape(label)}<strong>{html.escape(str(value))}</strong></div>"


def day_summary_row(row: dict[str, object]) -> str:
    return (
        "<tr>"
        f"<td>{row['day']}</td>"
        f"<td>{html.escape(str(row['pattern']))}</td>"
        f"<td>{float(row['inflow']):.2f}</td>"
        f"<td>{float(row['pumped']):.2f}</td>"
        f"<td>{float(row['cost']):.2f}</td>"
        f"<td>{float(row['min_volume']):.2f}</td>"
        f"<td>{float(row['max_volume']):.2f}</td>"
        f"<td>{row['outage_ticks']}</td>"
        f"<td>{row['warnings']}</td>"
        "</tr>"
    )


def interval_row(row: dict[str, str]) -> str:
    outage = []
    if row["p1_out_of_action"] == "true":
        outage.append("p1")
    if row["p2_out_of_action"] == "true":
        outage.append("p2")
    warnings = row["warnings"]
    return (
        "<tr>"
        f"<td>{html.escape(row['timestamp'])}</td>"
        f"<td>{html.escape(row['time_period'])}</td>"
        f"<td>{html.escape(row['tariff'])}</td>"
        f"<td>{html.escape(row['weather_pattern'])}</td>"
        f"<td>{html.escape(row['inflow'])}</td>"
        f"<td>{html.escape(','.join(outage) or '-')}</td>"
        f"<td>{html.escape(row['starting_volume'])}</td>"
        f"<td>{html.escape(row['ending_volume'])}</td>"
        f"<td>{html.escape(row['p1_status'])}</td>"
        f"<td>{html.escape(row['p1_rate'])}</td>"
        f"<td>{html.escape(row['p2_status'])}</td>"
        f"<td>{html.escape(row['p2_rate'])}</td>"
        f"<td>{html.escape(row['pumped_volume'])}</td>"
        f"<td>{html.escape(row['energy_cost'])}</td>"
        f"<td class=\"{'warn' if warnings else 'ok'}\">{html.escape(warnings or 'ok')}</td>"
        "</tr>"
    )


if __name__ == "__main__":
    main()
