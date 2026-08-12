# Repository guidance

## Delivery order

1. Implement backend contracts and domain models.
2. Implement individual security agents.
3. Implement orchestration and persistence.
4. Expose stable API contracts.
5. Implement frontend features against those contracts.

## Boundaries

- Domain code must not import framework or infrastructure code.
- Agents communicate through typed contracts, never through UI models.
- Device-affecting actions require an explicit policy and audit boundary.
- No frontend feature may invent an endpoint that is not defined by the backend contract.
- Secrets must never be committed.
