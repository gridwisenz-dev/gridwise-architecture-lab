from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


Status = Literal["Online", "Offline"]
StatusChange = Literal["Online", "Offline", "NoChange"]


class PumpConfig(BaseModel):
    id: str
    allowed_rates: list[float] = Field(min_length=1)

    @model_validator(mode="after")
    def require_zero_rate(self) -> "PumpConfig":
        if 0 not in self.allowed_rates:
            raise ValueError("allowed_rates must include 0")
        return self


class WellConfig(BaseModel):
    capacity: float = Field(gt=0)
    low_water_mark: float = Field(gt=0)
    high_water_mark: float = Field(gt=0)
    pumps: list[PumpConfig] = Field(min_length=1)
    status_lookback_ticks: int = Field(default=8, ge=1)
    max_status_changes_in_lookback: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def validate_marks(self) -> "WellConfig":
        if not self.low_water_mark < self.high_water_mark < self.capacity:
            raise ValueError("water marks must satisfy low < high < capacity")
        return self


class PumpState(BaseModel):
    id: str
    status: Status
    rate: float = Field(ge=0)
    recent_status_changes: list[StatusChange] = Field(default_factory=list)


class WellState(BaseModel):
    time: str
    volume: float = Field(ge=0)
    pumps: list[PumpState] = Field(min_length=1)


class ForecastPoint(BaseModel):
    time: str
    value: float = Field(ge=0)


class TariffPoint(BaseModel):
    time: str
    cost_per_kwh: float = Field(ge=0)


class PumpOutagePoint(BaseModel):
    time: str
    unavailable_pump_ids: list[str] = Field(default_factory=list)


class OptimizeRequest(BaseModel):
    config: WellConfig
    state: WellState
    inflow_forecast: list[ForecastPoint] = Field(min_length=1)
    tariff_forecast: list[TariffPoint] = Field(min_length=1)
    pump_outage_forecast: list[PumpOutagePoint] | None = None
    horizon_ticks: int = Field(default=24, ge=1, le=240)
    tick_minutes: int = Field(default=30, ge=1)
    switch_penalty: float = Field(default=0.05, ge=0)
    high_water_penalty: float = Field(default=100000.0, ge=0)
    low_water_penalty: float = Field(default=100.0, ge=0)
    max_search_states: int = Field(default=100, ge=1)


class PumpDecision(BaseModel):
    pump_id: str
    change_status: StatusChange
    status: Status
    rate: float


class PlanStep(BaseModel):
    tick: int
    time: str
    inflow: float
    tariff: float
    decisions: list[PumpDecision]
    starting_volume: float
    ending_volume: float
    pumped_volume: float
    energy_cost: float
    warnings: list[str] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    feasible: bool
    horizon_ticks: int
    tick_minutes: int
    total_energy_cost: float
    plan: list[PlanStep]
    warnings: list[str] = Field(default_factory=list)
