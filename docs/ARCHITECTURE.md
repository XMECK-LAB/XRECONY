# XRECONY Public Architecture

![Architecture](../assets/diagrams/architecture.svg)

## Boundaries

**Source:** readable input. XRECONY does not intentionally modify it.

**Workspace:** separate writable reconstruction state.

**Core:** passport/capture, relationships, generations, comparison, evidence and drift.

**Outputs:** reconstructed views, evidence, reports and—where supported—copy-first realization to a separate destination.

The public architecture intentionally omits private/internal governance and donor-history machinery.
