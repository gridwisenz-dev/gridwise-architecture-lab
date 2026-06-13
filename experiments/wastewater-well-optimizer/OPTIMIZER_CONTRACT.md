# Optimizer Contract

## Endpoint

`POST /optimize`

## What The Optimizer Does

The optimizer receives the current well state, well configuration, inflow forecast, and electricity tariff forecast. It returns a 12-hour pump operating plan at 30-minute intervals.

The caller should execute only the first 30-minute decision, update the well state, then call the optimizer again.

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
- default horizon is 24 intervals, which equals 12 hours

### Electricity Tariff Forecast

- electricity rate for each 30-minute interval
- tariff values should already be aligned to the month and tariff period

## Outputs Generated

### Feasibility

- whether a valid plan was found
- warning message if no valid plan exists

### 12-Hour Plan

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

- one optimizer call covers 12 hours
- each clock tick is 30 minutes
- the returned plan is advisory beyond the first tick
- the shell or caller is responsible for executing only the first tick and calling again
- tariff and inflow forecasts are provided by the caller

