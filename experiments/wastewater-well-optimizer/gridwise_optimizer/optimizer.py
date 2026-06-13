from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .models import (
    OptimizeRequest,
    OptimizeResponse,
    PlanStep,
    PumpDecision,
    Status,
    StatusChange,
    WellState,
)
from .simulator import SimulationError, simulate_tick


@dataclass(frozen=True)
class CandidatePlan:
    score: float
    energy_cost: float
    state: WellState
    plan: list[PlanStep]


def optimize(request: OptimizeRequest) -> OptimizeResponse:
    horizon = min(
        request.horizon_ticks,
        len(request.inflow_forecast),
        len(request.tariff_forecast),
    )
    warnings: list[str] = []
    candidates: dict[tuple, CandidatePlan] = {
        _state_key(request.state): CandidatePlan(
            score=0.0,
            energy_cost=0.0,
            state=request.state,
            plan=[],
        )
    }

    for tick in range(horizon):
        inflow = request.inflow_forecast[tick].value
        tariff = request.tariff_forecast[tick].cost_per_kwh
        next_time = request.inflow_forecast[tick].time

        next_inflow = (
            request.inflow_forecast[tick + 1].value
            if tick + 1 < len(request.inflow_forecast)
            else 0.0
        )
        unavailable_pumps = _unavailable_pumps(request, tick)
        next_candidates: dict[tuple, CandidatePlan] = {}

        for candidate in candidates.values():
            for decisions in _candidate_decisions(request, candidate.state, unavailable_pumps):
                try:
                    simulated = simulate_tick(
                        request.config,
                        candidate.state,
                        decisions,
                        inflow,
                        next_time,
                    )
                except SimulationError:
                    continue

                energy_cost = simulated.pumped_volume * tariff
                tick_score = _score_tick(
                    request=request,
                    starting_volume=candidate.state.volume,
                    ending_volume=simulated.ending_volume,
                    pumped_volume=simulated.pumped_volume,
                    tariff=tariff,
                    decisions=decisions,
                    next_inflow=next_inflow,
                )
                step = PlanStep(
                    tick=tick + 1,
                    time=next_time,
                    inflow=inflow,
                    tariff=tariff,
                    decisions=decisions,
                    starting_volume=candidate.state.volume,
                    ending_volume=simulated.ending_volume,
                    pumped_volume=simulated.pumped_volume,
                    energy_cost=round(energy_cost, 6),
                    warnings=simulated.warnings,
                )
                next_plan = CandidatePlan(
                    score=candidate.score + tick_score,
                    energy_cost=candidate.energy_cost + energy_cost,
                    state=simulated.state,
                    plan=[*candidate.plan, step],
                )
                key = _state_key(simulated.state)
                current = next_candidates.get(key)
                if current is None or next_plan.score < current.score:
                    next_candidates[key] = next_plan

        if not next_candidates:
            warnings.append(f"no feasible decision at tick {tick + 1}")
            return OptimizeResponse(
                feasible=False,
                horizon_ticks=horizon,
                tick_minutes=request.tick_minutes,
                total_energy_cost=0.0,
                plan=[],
                warnings=warnings,
            )

        candidates = _prune_candidates(next_candidates, request.max_search_states)

    if horizon < request.horizon_ticks:
        warnings.append("forecast length is shorter than requested horizon")

    best_plan = min(candidates.values(), key=lambda candidate: candidate.score)
    return OptimizeResponse(
        feasible=True,
        horizon_ticks=horizon,
        tick_minutes=request.tick_minutes,
        total_energy_cost=round(best_plan.energy_cost, 6),
        plan=best_plan.plan,
        warnings=warnings,
    )


def _choose_best_tick(
    request: OptimizeRequest,
    state: WellState,
    inflow: float,
    tariff: float,
    next_time: str,
    next_inflow: float,
    unavailable_pumps: set[str],
) -> tuple[list[PumpDecision], WellState, float, float, list[str]] | None:
    best_score: float | None = None
    best_result = None

    for decisions in _candidate_decisions(request, state, unavailable_pumps):
        try:
            simulated = simulate_tick(request.config, state, decisions, inflow, next_time)
        except SimulationError:
            continue

        score = _score_tick(
            request=request,
            starting_volume=state.volume,
            ending_volume=simulated.ending_volume,
            pumped_volume=simulated.pumped_volume,
            tariff=tariff,
            decisions=decisions,
            next_inflow=next_inflow,
        )
        if best_score is None or score < best_score:
            best_score = score
            best_result = (
                decisions,
                simulated.state,
                simulated.pumped_volume,
                simulated.ending_volume,
                simulated.warnings,
            )

    return best_result


def _candidate_decisions(
    request: OptimizeRequest,
    state: WellState,
    unavailable_pumps: set[str],
) -> list[list[PumpDecision]]:
    config_by_id = {pump.id: pump for pump in request.config.pumps}
    per_pump_options = []

    for current in state.pumps:
        options = []
        allowed_rates = sorted(config_by_id[current.id].allowed_rates)

        if current.id in unavailable_pumps:
            possible_statuses = ("Offline",)
        elif current.status == "Offline":
            possible_statuses = ("Online", "Offline")
        else:
            possible_statuses = ("Online",)

        for next_status in possible_statuses:
            rates = [0] if next_status == "Offline" else allowed_rates
            for rate in rates:
                change_status = _change_status(current.status, next_status)
                options.append(
                    PumpDecision(
                        pump_id=current.id,
                        change_status=change_status,
                        status=next_status,
                        rate=rate,
                    )
                )

        per_pump_options.append(options)

    return [list(candidate) for candidate in product(*per_pump_options)]


def _score_tick(
    request: OptimizeRequest,
    starting_volume: float,
    ending_volume: float,
    pumped_volume: float,
    tariff: float,
    decisions: list[PumpDecision],
    next_inflow: float,
) -> float:
    cost = pumped_volume * tariff
    switch_cost = request.switch_penalty * sum(
        1 for decision in decisions if decision.change_status != "NoChange"
    )

    high_penalty = 0.0
    if ending_volume > request.config.high_water_mark:
        high_penalty = (
            request.config.capacity * request.high_water_penalty
            + (ending_volume - request.config.high_water_mark) * request.high_water_penalty
        )

    low_penalty = 0.0
    if ending_volume < request.config.low_water_mark:
        low_penalty = (request.config.low_water_mark - ending_volume) * request.low_water_penalty

    # Bias toward action before the well approaches the high mark.
    trend_penalty = 0.0
    if starting_volume >= request.config.high_water_mark and ending_volume >= starting_volume:
        trend_penalty = request.high_water_penalty

    headroom_penalty = 0.0
    if ending_volume + next_inflow >= request.config.capacity:
        headroom_penalty = request.config.capacity * request.high_water_penalty

    return cost + switch_cost + high_penalty + low_penalty + trend_penalty + headroom_penalty


def _change_status(current: Status, next_status: str) -> StatusChange:
    if current == next_status:
        return "NoChange"
    if next_status == "Online":
        return "Online"
    return "Offline"


def _prune_candidates(
    candidates: dict[tuple, CandidatePlan],
    max_states: int,
) -> dict[tuple, CandidatePlan]:
    if len(candidates) <= max_states:
        return candidates
    best_items = sorted(candidates.items(), key=lambda item: item[1].score)[:max_states]
    return dict(best_items)


def _state_key(state: WellState) -> tuple:
    pump_key = tuple(
        (
            pump.id,
            pump.status,
            round(pump.rate, 6),
            tuple(pump.recent_status_changes),
        )
        for pump in sorted(state.pumps, key=lambda item: item.id)
    )
    return (round(state.volume, 2), pump_key)


def _unavailable_pumps(request: OptimizeRequest, tick: int) -> set[str]:
    if request.pump_outage_forecast is None or tick >= len(request.pump_outage_forecast):
        return set()
    return set(request.pump_outage_forecast[tick].unavailable_pump_ids)
