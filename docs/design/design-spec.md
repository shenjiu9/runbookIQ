# RunbookIQ dashboard design specification

Concept source: `runbookiq-dashboard-concept.png` (1536 × 1024).

## Color lock

- Background: deep navy `#071520`
- Sidebar: `#06131d`
- Panels: `#0a1b28`
- Elevated row: `#0d2231`
- Border: `#1c3a4d`
- Primary text: `#f4f7fa`
- Secondary text: `#8da2b2`
- Cyan accent: `#2aa8ff`
- Success: `#59d88b`
- Warning: `#f0b429`

No glassmorphism, no warm off-white, and no decorative color overlays.

## Typography

- UI and content: Inter, `Segoe UI`, sans-serif
- Commands and scores: `IBM Plex Mono`, `Cascadia Code`, monospace
- Page title: 25 px / 700
- Panel title: 13 px / 650
- Body: 13 px / 1.65
- Utility labels: 11–12 px / 500

## Container model

- Fixed 184 px sidebar.
- 52 px top bar.
- Main area uses a two-column grid: fluid investigation column and 420 px evidence inspector.
- Panels are open rectangular regions with 1 px borders and 8 px radius.
- Tables and rails are preferred over nested cards.

## Allowed primary-screen copy

- RunbookIQ
- Ask, Knowledge, Ingestion, Evaluation, Settings
- Platform Engineering
- System health, All systems operational
- Investigate an incident
- Why are pods stuck in CrashLoopBackOff after a config rollout?
- Source scope, All sources
- Run
- Generated answer, Confidence
- Top supporting sources
- Retrieval & generation trace
- Evaluation summary
- Evidence, Trace, Open source
- Ingestion status

## Icon inventory

Use Lucide outline icons at 16–18 px with 1.7 px stroke: MessageSquare, Library,
Database, ChartNoAxesCombined, Settings, Network, CircleHelp, Bell, Play, FileText,
ExternalLink, Check, LoaderCircle, Copy, ThumbsUp, ThumbsDown.

## Core interaction

1. User selects a knowledge base and submits a question.
2. Answer, confidence, citations, trace, and evidence inspector update from `/api/query`.
3. Selecting a source row changes the evidence inspector.
4. Evidence/Trace tabs switch the right panel.
5. Sidebar exposes functional ingestion and evaluation views without changing the primary design system.

