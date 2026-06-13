from __future__ import annotations

from dataclasses import dataclass

from .models import PumpDecision, StatusChange, WellConfig, WellState


@dataclass(frozen=True)
class SimulatedTick:
    state: WellState
    pumped_volume: float
    ending_volume: float
    warnings: list[str]


class SimulationError(ValueError):
    pass


def validate_state(config: WellConfig, state: WellState) -> None:
    pump_configs = {pump.id: pump for pump in config.pumps}
    if set(pump_configs) != {pump.id for pump in state.pumps}:
        raise SimulationError("state pumps must match config pumps")
    if state.volume >= config.capacity:
        raise SimulationError("well volume must be below capacity")
    if not any(pump.status == "Online" for pump in state.pumps):
        raise SimulationError("at least one pump must be online")

    for pump in state.pumps:
        allowed_rates = pump_configs[pump.id].allowed_rates
        if pump.rate not in allowed_rates:
            raise SimulationError(f"pump {pump.id} rate is not allowed")
        if pump.status == "Offline" and pump.rate != 0:
            raise SimulationError(f"pump {pump.id} is offline and must have rate 0")
        if count_recent_switches(pump.recent_status_changes) > config.max_status_changes_in_lookback:
            raise SimulationError(f"pump {pump.id} exceeds recent switching limit")


def simulate_tick(
    config: WellConfig,
    state: WellState,
    decisions: list[PumpDecision],
    inflow: float,
    next_time: str,
) -> SimulatedTick:
    validate_state(config, state)

    decision_by_id = {decision.pump_id: decision for decision in decisions}
    current_by_id = {pump.id: pump for pump in state.pumps}
    config_by_id = {pump.id: pump for pump in config.pumps}

    if set(decision_by_id) != set(current_by_id):
        raise SimulationError("decisions must match state pumps")

    volume_after_inflow = state.volume + inflow
    if volume_after_inflow >= config.capacity:
        raise SimulationError("inflow would overflow the well before pumping")

    next_pumps = []
    total_pumped = 0.0
    warnings: list[str] = []

    for pump_id, current in current_by_id.items():
        decision = decision_by_id[pump_id]
        if decision.change_status not in _allowed_change(current.status, decision.status):
            raise SimulationError(f"pump {pump_id} status change is inconsistent")
        if decision.rate not in config_by_id[pump_id].allowed_rates:
            raise SimulationError(f"pump {pump_id} rate is not allowed")
        if decision.status == "Offline" and decision.rate != 0:
            raise SimulationError(f"pump {pump_id} is offline and must have rate 0")

        recent = [decision.change_status, *current.recent_status_changes]
        recent = recent[: config.status_lookback_ticks]
        if count_recent_switches(recent) > config.max_status_changes_in_lookback:
            raise SimulationError(f"pump {pump_id} exceeds recent switching limit")

        total_pumped += decision.rate
        next_pumps.append(
            current.model_copy(
                update={
                    "status": decision.status,
                    "rate": decision.rate,
                    "recent_status_changes": recent,
                }
            )
        )

    if not any(pump.status == "Online" for pump in next_pumps):
        raise SimulationError("at least one pump must remain online")

    ending_volume = volume_after_inflow - total_pumped
    if ending_volume < 0:
        raise SimulationError("plan pumps more water than available")
    if ending_volume >= config.capacity:
        raise SimulationError("plan causes well overflow")
    if ending_volume > config.high_water_mark:
        warnings.append("ending volume is above high water mark")
    if ending_volume < config.low_water_mark:
        warnings.append("ending volume is below low water mark")

    next_state = WellState(time=next_time, volume=ending_volume, pumps=next_pumps)
    return SimulatedTick(
        state=next_state,
        pumped_volume=total_pumped,
        ending_volume=ending_volume,
        warnings=warnings,
    )


def count_recent_switches(changes: list[StatusChange]) -> int:
    return sum(1 for change in changes if change != "NoChange")


def _allowed_change(current_status: str, next_status: str) -> set[StatusChange]:
    if current_status == next_status:
        return {"NoChange"}
    return {next_status}

