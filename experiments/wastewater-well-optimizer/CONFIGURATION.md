# Configuration Reference

This document records the current file formats and values used by the wastewater well optimizer experiment.

## Optimizer Request

File: `samples/optimizer_request.json`

The sample request follows the current publication mode:

- 2 days of forecast inputs
- 96 intervals
- 30 minutes per interval
- 12 hours executed before the caller re-optimizes

Top-level fields:

| Field | Purpose | Current Value |
| --- | --- | --- |
| `config` | Static well and pump rules. | See Well Configuration. |
| `state` | Current well and pump state. | Starts at `2026-06-01T00:00:00+00:00`. |
| `inflow_forecast` | Expected wastewater inflow by interval. | 96 half-hour values. |
| `tariff_forecast` | Electricity tariff by interval. | 96 half-hour values. |
| `pump_outage_forecast` | Pump availability by interval. | 96 half-hour values. |
| `horizon_ticks` | Number of forecast intervals optimized. | `96`. |
| `tick_minutes` | Interval length. | `30`. |
| `max_search_states` | Beam-search width for bounded optimization. | `100`. |

## Well Configuration

Current values:

| Field | Value | Meaning |
| --- | ---: | --- |
| `capacity` | `320` | Maximum well volume. |
| `low_water_mark` | `45` | Lower operating boundary. |
| `high_water_mark` | `235` | Upper operating boundary. |
| `status_lookback_ticks` | `24` | Previous 12 hours of pump status history. |
| `max_status_changes_in_lookback` | `6` | Maximum on/off changes within the lookback window. |

Pump configuration:

| Pump | Allowed Rates |
| --- | --- |
| `p1` | `0`, `4`, `8`, `12`, `16` |
| `p2` | `0`, `4`, `8`, `12`, `16` |

## Initial State

Current sample state:

| Field | Value |
| --- | --- |
| `time` | `2026-06-01T00:00:00+00:00` |
| `volume` | `135` |
| `p1.status` | `Online` |
| `p1.rate` | `0` |
| `p2.status` | `Online` |
| `p2.rate` | `0` |
| pump history | 24 `NoChange` entries per pump |

## Forecast Inputs

All forecast arrays must align by index and time.

Each 30-minute interval should have:

- one expected inflow value
- one tariff value
- one pump outage entry

For current publication mode, each request should contain 96 intervals, which equals 2 days.

## Electricity Tariff Matrix

File: `data/electricity_tariff.csv`

Format:

| Column | Meaning |
| --- | --- |
| `month` | Month name, Jan-Dec. |
| `T1-T8` | Tariff for periods 1-8. |
| `T9-T16` | Tariff for periods 9-16. |
| `T17-T24` | Tariff for periods 17-24. |
| `T25-T32` | Tariff for periods 25-32. |
| `T33-T40` | Tariff for periods 33-40. |
| `T41-T48` | Tariff for periods 41-48. |

Each tariff band covers 8 half-hour periods, or 4 hours.

## Scenario Input File

File: `data/optimizer_30_day_input.csv`

Format:

| Column | Meaning |
| --- | --- |
| `tick` | 1-based interval number. |
| `timestamp` | Interval start time. |
| `interval_end` | Interval end time. |
| `day` | 1-based scenario day. |
| `time_period` | Half-hour period, `T1` to `T48`. |
| `tariff_band` | 4-hour tariff band. |
| `tariff` | Electricity tariff for the interval. |
| `weather_pattern` | Dry/wet/extreme weather scenario label. |
| `inflow` | Actual inflow for the interval. |
| `p1_out_of_action` | Whether pump `p1` is unavailable. |
| `p2_out_of_action` | Whether pump `p2` is unavailable. |

## Current Scenario Assumptions

- 30-day scenario
- 1,440 half-hour intervals
- low night inflows
- high morning and evening inflows
- wet weather can override the normal daily inflow shape
- one pump is out of action for 25% of intervals
- both pumps are never out at the same time
- expected inflows in the current comparison are conservative and within 10% above actual inflows

