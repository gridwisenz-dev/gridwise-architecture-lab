# Optimizer Contract

## Endpoint

`POST /optimise`

Compatibility alias:

`POST /optimize`

## What The Optimizer Does

The optimizer receives the current well state, well configuration, inflow forecast, electricity tariff forecast, and pump outage forecast. It returns a pump operating plan at 30-minute intervals across the supplied forecast horizon.

For the current publication path, the caller should pass the next 2 days of forecast data, execute the first 12 hours of the returned plan, update the well state, then call the optimizer again with a refreshed 2-day forecast.

## Inputs Required

### Current Well State

- current clock time
- current well volume
- current status of each pump: online or offline
- current operating rate of each pump
- recent on/off history for each pump

### Static Well Configuration

- well capacity
- low water mark
- high water mark
- list of pumps
- allowed operating rates for each pump
- number of previous ticks used for switching history
- maximum allowed pump status changes within that lookback window

### Inflow Forecast

- expected incoming wastewater volume for each 30-minute interval
- current publication mode expects 96 intervals, which equals 2 days
- the API default is 24 intervals, which equals 12 hours, if no horizon is specified

### Electricity Tariff Forecast

- electricity rate for each 30-minute interval
- tariff values should already be aligned to the month and tariff period
- current publication mode expects the next 2 days of tariff values

### Pump Outage Forecast

- unavailable pump IDs for each 30-minute interval
- this captures planned or expected pump outages
- if omitted, the optimizer assumes all pumps are available

## Outputs Generated

### Feasibility

- whether a valid plan was found
- warning message if no valid plan exists

### Forecast-Horizon Plan

For each 30-minute interval:

- interval number
- interval time
- inflow used
- tariff used
- pump status decision for each pump
- pump rate decision for each pump
- starting well volume
- ending well volume
- pumped volume
- interval energy cost
- warnings, if any

### Total Cost

- total expected energy cost across the returned plan

## Rules Enforced

- well volume must stay below capacity
- inflow must not overflow the well before pumping
- offline pumps must have rate zero
- pump rates must be valid allowed rates
- at least one pump must remain online
- pump switching must stay within the configured recent-switching limit

## Current Assumptions

- current publication mode passes 2 days of forecast input per optimizer call
- the caller executes the first 12 hours of the returned plan before calling again
- each clock tick is 30 minutes
- the returned plan is advisory beyond the first 12 hours
- tariff and inflow forecasts are provided by the caller
- expected inflows used in the current comparison are conservative and within 10% above actuals
