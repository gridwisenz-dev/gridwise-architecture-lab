# Gridwise Architecture Details

## Purpose

Capture the system architecture, key design decisions, operating assumptions, and implementation details for Gridwise.

## System Context

Describe what Gridwise does, who uses it, and which external systems it depends on.

- Primary users:
- Core workflows:
- External integrations:
- Critical constraints:

## Architecture Overview

Summarize the system at a high level.

- Frontend:
- Backend: Optimizer Shell coordinates simulator validation and optimizer plan execution.
- Data storage:
- Background jobs:
- Third-party services: Optimizer service, reachable by URL, expected to return plans across the supplied forecast horizon.
- Deployment target:

## Core Domains

List the major product or business domains and the responsibilities owned by each.

| Domain | Responsibility | Key Data | Notes |
| --- | --- | --- | --- |
| Optimizer Shell | Orchestrates simulator runs and repeated optimizer calls. | Config, state, inflow, optimizer plan, simulator results. | Implemented with fake input data so far. |
| Simulator | Validates whether historical input data can be executed against the modeled system. | Input data file, modeled system state, simulator errors. | Error-free execution is necessary but not sufficient for simulator and data correctness. |
| Optimizer | Produces cost-minimized pump plans across the supplied forecast horizon. | Config, state, inflow forecast, tariff forecast, pump outage forecast, plan. | Current publication mode passes 2 days of forecast data and executes the first 12 hours. |

## Components

Document each major component, service, module, or package.

### Optimizer Shell

- Responsibility: Coordinate simulator validation and optimizer-driven execution.
- Inputs: Input data file, config, state, inflow.
- Outputs: Simulator run result, optimizer plan, executed plan interval.
- Dependencies: Simulator, Optimizer service, `/ClockTick` endpoint.
- Failure modes: Simulator returns an error because the system model is inaccurate or the input data is incorrect.
- Owner:

### Simulator

- Responsibility: Execute historical input data against the modeled system.
- Inputs: Input data file.
- Outputs: Success or simulator error.
- Dependencies: Current system model.
- Failure modes: Returns errors for invalid data or inaccurate system modeling.
- Owner:

### Optimizer

- Responsibility: Return a cost-minimized pump plan across the supplied forecast horizon.
- Inputs: Config, state, inflow forecast, tariff forecast, pump outage forecast.
- Outputs: Plan.
- Dependencies: Optimizer endpoint URL.
- Failure modes: Missing endpoint, invalid request contract, invalid plan response.
- Owner:

## Data Model

Describe the important entities, relationships, and storage rules.

| Entity | Purpose | Important Fields | Relationships |
| --- | --- | --- | --- |
| Input data file | Provides historical data to run through the simulator. | Schema TBD. | Consumed by Simulator through Optimizer Shell. |
| Config | Optimizer input describing operating constraints and settings. | TBD. | Sent to Optimizer with state and inflow. |
| State | Optimizer input describing current system state. | TBD. | Sent to Optimizer with config and inflow. |
| Inflow forecast | Optimizer input describing expected incoming wastewater. | One value per 30-minute interval. | Current publication mode passes 96 intervals, which equals 2 days. |
| Tariff forecast | Optimizer input describing electricity cost. | One tariff value per 30-minute interval. | Derived from the month by 4-hour tariff matrix. |
| Pump outage forecast | Optimizer input describing pump availability. | Unavailable pump IDs per 30-minute interval. | Omitted means all pumps are available. |
| Plan | Optimizer output for the supplied forecast horizon. | Pump status, pump rate, volume, pumped amount, interval cost. | Current publication mode executes the first 12 hours, then re-optimizes. |

## Data Flows

Document the most important request, event, and background processing flows.

### Flow Name

1. Trigger:
2. Validation:
3. Processing:
4. Persistence:
5. Side effects:
6. Response or completion:

### Historical Simulator Validation

1. Trigger: Optimizer Shell receives an input data file.
2. Validation: Simulator executes the file against the modeled system.
3. Processing: Each historical data point is run through the simulator.
4. Persistence: TBD.
5. Side effects: Simulator may expose model or data errors.
6. Response or completion: Error-free simulator run indicates a necessary but not sufficient condition for simulator and data correctness.

### 2-Day Forecast Optimizer Execution

1. Trigger: Caller has config, current state, 2-day inflow forecast, 2-day tariff forecast, and pump outage forecast.
2. Validation: Optimizer request must match the agreed request schema.
3. Processing: Optimizer returns a cost-minimized plan across the supplied 2-day forecast horizon.
4. Persistence: TBD.
5. Side effects: Caller executes the first 12 hours of the returned plan against actual inflows.
6. Response or completion: Repeat with updated state and refreshed 2-day forecasts.

## APIs And Contracts

Capture public interfaces, internal contracts, and integration boundaries.

| Interface | Consumer | Producer | Contract | Notes |
| --- | --- | --- | --- | --- |
| Optimizer plan request | Caller or Optimizer Shell | Optimizer | Request contains config, state, inflow forecast, tariff forecast, and optional pump outage forecast. | Current publication mode passes 2 days of 30-minute intervals. |
| Optimizer plan response | Caller or Optimizer Shell | Optimizer | Returns a plan across the supplied forecast horizon. | Caller executes the first 12 hours before re-optimizing. |
| `/ClockTick` | Caller or Optimizer Shell | Simulator or system runtime | Execute selected plan intervals. | Current comparison executes 12 hours, not only one tick. |

Example plan for time horizon 1:

```json
{
  "P": [
    {
      "ChangeStatus": "Off"
    },
    {
      "ChangeStatus": "NoChange",
      "Rate": 1
    }
  ],
  "inflow": 2
}
```

## Non-Functional Requirements

- Availability:
- Latency:
- Throughput:
- Security:
- Privacy:
- Compliance:
- Observability:
- Cost constraints:

## Deployment Architecture

Describe environments, hosting, release flow, and rollback strategy.

- Environments:
- Build pipeline:
- Release process:
- Rollback process:
- Secrets management:

## Security Model

Document authentication, authorization, data protection, and audit behavior.

- Authentication:
- Authorization:
- Sensitive data:
- Audit logging:
- Threat assumptions:

## Observability

Document how the system is monitored and debugged.

- Logs:
- Metrics:
- Traces:
- Alerts:
- Dashboards:

## Architecture Decisions

Record important decisions in short form. Move larger decisions into ADR files if needed.

| Date | Decision | Rationale | Consequences |
| --- | --- | --- | --- |
| 2026-06-13 | Start architecture detail log | Establish a shared place for system design detail before implementation choices are locked in. | Keeps decisions explicit and reviewable. |
| 2026-06-13 | Use Optimizer Shell as the orchestration boundary | The shell already coordinates simulator validation, optimizer calls, and `/ClockTick` execution. | Optimizer and simulator contracts need to be made explicit. |

## Open Questions

- What is the first user-facing workflow Gridwise needs to support?
- What is the schema for the real input data file?
- Where will the real input data file come from?
- What URL should the Optimizer Shell call to get optimizer plans?
- What is the exact request schema for config, state, inflow forecast, tariff forecast, and pump outage forecast?
- What is the exact `/ClockTick` request schema?
- What deployment environment should the initial system target?
