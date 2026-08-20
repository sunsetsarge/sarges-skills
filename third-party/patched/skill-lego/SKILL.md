---
name: skill-lego
description: "LEGO set research, part lookups, pricing, and inventory management using BrickLink, Rebrickable, and LEGO.com. Trigger on LEGO, minifig, minifigure, BrickLink, Rebrickable, MOC, or LEGO set price/value/parts questions; do NOT trigger on bare 'set', 'brick', or 'price' in non-LEGO contexts. Also trigger when comparing LEGO set values, checking part availability, or researching LEGO investments."
---

# LEGO Integration Skill

**Confluence sources for auto-sync:**

| Source Page | Page ID | Content |
|-------------|---------|---------|
| LEGO Integration Protocol | 14778418 | Data sources, workflows, formats |

**Last synced:** 2026-04-17 | **Source version:** v1.0

## Environment note
Paths like C:\... and D:\... are Blaine's Windows machine. In a remote/Cowork Linux session, reach them via the remote-device tools (device_bash / Desktop Commander), never the local Bash tool. Ports and paths were verified on the Windows box only. Any 'Last synced' tables are provenance only — do not attempt to sync; if a rule conflicts with observed reality, trust reality and flag for re-sync.

---

## Data Sources

| Source | Use For |
|--------|---------|
| BrickLink | Pricing, market value, part inventory, historical prices |
| Rebrickable | Set inventory, part lists, MOC data, alternate builds |
| LEGO.com | Retail pricing, current availability, retirement status |

Access method: no API keys are configured for BrickLink or Rebrickable — use web search/fetch on the public pages (BrickLink catalog + price guide, Rebrickable set pages). If Blaine later adds API keys, record them here and prefer the APIs.

---

## Standard Workflow

1. Identify the set number or part ID from user request
2. Search the appropriate source based on data needed
3. Present results in structured format (below)
4. Log findings to LEGO Project Log if part of an ongoing project

---

## Set Research Format

```
### [Set Number] — [Set Name]
- Year: [year]
- Pieces: [count]
- Retail: $[price]
- BrickLink avg (used): $[price]
- BrickLink avg (new): $[price]
- Notes: [anything notable — retirement status, rare minifigs, price trend]
```

## Part Research Format

```
### Part [ID] — [Part Name]
- Color: [color]
- BrickLink avg: $[price]
- Availability: [common / rare]
- Notes: [usage, sets it appears in, alternates]
```

## Minifigure Research Format

```
### [Minifig ID] — [Character Name]
- Appears in: [set numbers]
- BrickLink avg (new): $[price]
- BrickLink avg (used): $[price]
- Exclusive: [yes/no — which set]
- Notes: [variants, print differences, rarity]
```

---

## Storage

Save all LEGO research to: `C:\Claude\Interests\LEGO\`. In a remote session with no device access, save to the KB (knowledge/ or projects/) and note it needs syncing.
