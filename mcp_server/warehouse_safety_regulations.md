# Warehouse Safety Regulations

**Policy ID:** 2
**Applicable Department:** Warehouse
**Effective Date:** 2026-01-01
**Owner:** IronBridge Construction — Warehouse & Safety Office

## Purpose

This policy sets access control, fire safety, and stacking-height
requirements for all IronBridge warehouse locations, and defines the
minimum-stock workflow that governs when a material reservation is
allowed to proceed without further sign-off.

## Access Control

- Only employees with an active Warehouse Supervisor session may
  authorize the physical release of reserved material from a warehouse.
- Site Engineers and Procurement Officers may view inventory and submit
  purchase requests, but may not authorize a reservation or dispatch.
- Cross-project staff (Finance Officers, Warehouse Supervisors) may act
  on any warehouse location; Project Managers are scoped to the
  warehouse(s) serving their own project.

## Fire Safety

- Flammable materials (solvents, certain electrical insulation stock)
  must be stored at least 3 meters from any ignition source and within
  a designated fire-rated storage zone.
- Warehouse aisles must remain clear of stacked material at all times
  to preserve emergency egress routes.

## Stacking Height

- Palletized cement and concrete block stacks: maximum 4 pallets high.
- Steel bundles: maximum 2 bundles high unless racked.
- No stack may exceed 80% of the rated height of the racking system in
  use.

## Minimum Stock Level Workflow

Every material in inventory has a `MinimumStockLevel` — the floor
below which the warehouse is no longer considered to hold a safe
operating buffer for ongoing projects. This exists because construction
material lead times (weeks, for some steel and electrical stock) mean
that running out mid-project is a schedule risk, not just an
inconvenience.

**Rule:** a material reservation that would drop `QuantityAvailable`
below `MinimumStockLevel` is **not blocked outright**, but it is never
auto-approved silently either. The Warehouse Supervisor processing the
reservation must be shown the resulting stock level and give explicit
confirmation before the reservation proceeds. This is a deliberate
human-in-the-loop checkpoint — the system will surface the numbers, but
a person makes the call on whether the operational risk is acceptable
for that specific project's timeline.

This is distinct from budget escalation (a Project Manager / Finance
concern) — low-stock confirmation is a Warehouse Supervisor decision
about physical inventory risk, not a financial one, and the two
approval paths do not substitute for one another.

## Incident Reporting

Any breach of access control, fire safety zoning, or stacking limits
must be logged and escalated to the Warehouse Supervisor on duty within
the same shift it is discovered.
