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
- Third-party services: Optimizer service, reachable by URL, expected to return plans for fixed time horizons.
- Deployment target:

## Core Domains

List the major product or business domains and the responsibilities owned by each.

| Domain | Responsibility | Key Data | Notes |
| --- | --- | --- | --- |
| Optimizer Shell | Orchestrates simulator runs and repeated optimizer calls. | Config, state, inflow, optimizer plan, simulator results. | Implemented with fake input data so far. |
| Simulator | Validates whether historical input data can be executed against the modeled system. | Input data file, modeled system state, simulator errors. | Error-free execution is necessary but not sufficient for simulator and data correctness. |
| Optimizer | Produces plans across a fixed number of time horizons. | Config, state, inflow, plan. | Needs a real URL endpoint. |

## Components

Document each major component, service, module, or package.

### Optimizer Shell

- Responsibility: Coordinate simulator validation and optimizer-driven execution.
- Inputs: Input data file, config, state, inflow.
- Outputs: Simulator run result, optimizer plan, `/ClockTick` execution for the first time horizon.
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

- Responsibility: Return a plan for a fixed number of time horizons.
- Inputs: Config, state, inflow.
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
| Inflow | Optimizer input describing current inflow. | Numeric inflow value. | Sent to Optimizer and also appears in the returned plan example. |
| Plan | Optimizer output for fixed time horizons. | `P`, `ChangeStatus`, optional `Rate`, `inflow`. | Time horizon 1 is executed via `/ClockTick`. |

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

### Receding-Horizon Optimizer Execution

1. Trigger: Optimizer Shell has config, state, and inflow.
2. Validation: Optimizer request must match the agreed request schema.
3. Processing: Optimizer returns a plan for a fixed number of time horizons.
4. Persistence: TBD.
5. Side effects: Optimizer Shell executes `/ClockTick` using the plan for time horizon 1.
6. Response or completion: Repeat with updated config, state, and inflow.

## APIs And Contracts

Capture public interfaces, internal contracts, and integration boundaries.

| Interface | Consumer | Producer | Contract | Notes |
| --- | --- | --- | --- | --- |
| Optimizer plan request | Optimizer Shell | Optimizer | Request contains config, state, and inflow. | Exact schema TBD. |
| Optimizer plan response | Optimizer Shell | Optimizer | Returns plans for fixed time horizons. | URL needed. |
| `/ClockTick` | Optimizer Shell | Simulator or system runtime | Execute plan for time horizon 1. | Exact request schema TBD. |

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
- What is the exact request schema for config, state, and inflow?
- What is the exact `/ClockTick` request schema?
- What deployment environment should the initial system target?
