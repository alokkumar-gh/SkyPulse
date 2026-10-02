# SkyPulse — UI/UX Specification

**Version:** 1.0  
**Framework:** React 18 + TypeScript  
**Map:** MapLibre GL JS  
**Charts:** Recharts  
**State:** Zustand  
**Real-time:** Socket.io-client  
**Status:** Implementation-Ready

---

## Design Philosophy

SkyPulse is an **operational intelligence platform**, not a consumer app. The design must convey authority, clarity, and information density without visual noise.

**Design principles:**
1. **Information-first:** Every pixel earns its place. No decorative cards, no gratuitous gradients.
2. **Operational clarity:** Analysts should instantly understand event severity, status, and location.
3. **Responsive alert design:** Critical states (unverified high-severity events) must be visually prominent.
4. **Real-time as default:** The dashboard should feel alive — map markers update, counts change, the pipeline is visible.
5. **Consistent visual language:** Severity, verification status, and source type have consistent visual encoding across all screens.

---

## Design System

### Color Palette

```css
/* Background */
--bg-primary:    #0a0e1a;   /* Dark navy — page background */
--bg-surface:    #111827;   /* Slightly lighter — cards, panels */
--bg-elevated:   #1c2537;   /* Modals, dropdowns */
--bg-border:     #2a3548;   /* Borders, dividers */

/* Text */
--text-primary:  #e8edf5;   /* Primary text */
--text-secondary:#8b96a8;   /* Secondary, labels */
--text-muted:    #5a6478;   /* Disabled, placeholder */

/* Brand */
--brand-blue:    #3b82f6;   /* Primary interactive */
--brand-blue-dim:#1e3a5f;   /* Brand backgrounds */

/* Severity Colors */
--severity-1:    #22c55e;   /* Minor — Green */
--severity-2:    #eab308;   /* Moderate — Amber */
--severity-3:    #f97316;   /* Severe — Orange */
--severity-4:    #ef4444;   /* Extreme — Red */

/* Verification Status Colors */
--status-verified:    #22c55e;
--status-likely:      #3b82f6;
--status-unverified:  #8b96a8;
--status-contradicted:#ef4444;
--status-review:      #f97316;

/* Event Category Colors */
--cat-rainfall:    #60a5fa;
--cat-thunderstorm:#a78bfa;
--cat-flooding:    #2563eb;
--cat-heatwave:    #f97316;
--cat-fog:         #94a3b8;
--cat-dust-storm:  #d97706;
--cat-strong-winds:#34d399;

/* Demo Mode */
--demo-badge:      #7c3aed;
```

### Typography

```css
/* Import: Google Fonts — Inter */
--font-sans: 'Inter', -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', monospace;

/* Scale */
--text-xs:  0.75rem;    /* 12px — labels, badges */
--text-sm:  0.875rem;   /* 14px — body, table cells */
--text-base:1rem;       /* 16px — default */
--text-lg:  1.125rem;   /* 18px — section headers */
--text-xl:  1.25rem;    /* 20px — card titles */
--text-2xl: 1.5rem;     /* 24px — page headers */
--text-3xl: 1.875rem;   /* 30px — metric numbers */
```

### Visual Encoding Standards

These must be applied consistently across all screens:

**Severity Badge:** Colored dot + number: `● 3` in `--severity-3` color  
**Verification Status Chip:** Small pill with icon: `✓ VERIFIED` / `~ LIKELY` / `? UNVERIFIED` / `✗ CONTRADICTED` / `⚠ REVIEW`  
**Source Type Icon:** Icon beside source name (cloud = API, person = citizen, dataset icon = dataset, ⚙ = demo)  
**Demo Watermark:** Purple `DEMO` badge on any card containing demo data

---

## Layouts

### Global Layout

```
┌─────────────────────────────────────────────────────┐
│  TOPBAR: Logo | Nav Links | Alerts Bell | User Menu │
├──────────┬──────────────────────────────────────────┤
│          │                                          │
│ SIDEBAR  │         MAIN CONTENT AREA                │
│ (240px)  │                                          │
│          │                                          │
└──────────┴──────────────────────────────────────────┘
```

- Sidebar collapses to icon-only on mobile
- Topbar is fixed; sidebar scrollable
- Main content area scrollable independently

### Topbar Items

- **Left:** SkyPulse logo + "NATIONAL WEATHER INTELLIGENCE" tagline (small, muted)
- **Center:** `[Live Map] [Events] [Analytics] [Reports]` — role-dependent additional items
- **Right:** Real-time ingestion counter (animates on new data), notification bell with unread count, user avatar + menu

### Sidebar Items (role-dependent)

```
PUBLIC / CITIZEN:
  ◉ Live Map
  ◉ Events
  ◉ Analytics
  ◉ Submit Report

ANALYST adds:
  ◉ Verification Queue
  ◉ Duplicate Clusters
  ◉ DWEG Intelligence

ADMIN adds:
  ◉ Admin Panel
  ◉ Connectors
  ◉ Users
  ◉ Audit Log
  ◉ System Health
```

---

## Screen 1 — Public Dashboard (Live Map)

### Purpose
The primary operational view. Shows all active weather events on the India map with real-time updates.

### Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  TOPBAR                                                          │
├────────────────────────┬─────────────────────────────────────────┤
│  SIDEBAR               │  INDIA MAP (MapLibre GL)                │
│                        │                                          │
│  ─ ACTIVE EVENTS ─     │  [Event markers, clusters, heatmap]     │
│  47 total              │                                          │
│  23 Verified           │                                          │
│  8 Anomalous           │  ┌─────────────────────────────────┐    │
│                        │  │ EVENT FEED (right sidebar)      │    │
│  ─ BY CATEGORY ─       │  │ Scrollable list of recent events│    │
│  ▐ Rainfall   12       │  │ Auto-updates in real time       │    │
│  ▐ Flooding   10       │  └─────────────────────────────────┘    │
│  ▐ Thunderst   8       │                                          │
│  ▐ Heatwave    5       │                                          │
│  ...                   │                                          │
│                        │  MAP CONTROLS: +/- zoom, India fit,     │
│  ─ FILTERS ─           │  Heatmap toggle, Layer selector         │
│  [Date range]          │                                          │
│  [Category]            │                                          │
│  [State]               │                                          │
│  [Status]              │                                          │
│  [Severity]            │                                          │
│  [Source]              │                                          │
│  [Confidence]          │                                          │
└────────────────────────┴─────────────────────────────────────────┘
```

### Map Layers (toggleable)

1. **Event Markers:** Custom SVG markers colored by category, sized by severity, icon by verification status
2. **Cluster Layer:** Auto-clusters markers at low zoom, shows event count badge
3. **Heatmap Layer:** Report density heatmap (MapLibre heatmap layer)
4. **State Boundaries:** Subtle boundary lines

### Map Marker Design

- Shape: Hexagon (distinctive from standard circular markers)
- Color: Matches `--cat-{category}` color
- Size: 24px (severity 1–2) → 32px (severity 3–4)
- Border: Verification status color ring
- Icon: Small weather icon inside hexagon

### Event Feed (Right Panel)

Each card in the feed:
```
┌─────────────────────────────────────────┐
│ 🌊 FLOODING · Severe                    │
│ Chennai, Tamil Nadu                      │
│ 8 reports · VERIFIED ✓                  │
│ 15 min ago                    [View →]  │
└─────────────────────────────────────────┘
```

New events slide in at the top with a subtle animation. Card border pulses once on new arrival.

### States

- **Loading:** Skeleton map with spinner, "Connecting to SkyPulse..." message
- **Empty (no events):** Map centered on India, "No active events in selected period" overlay
- **No connection:** Banner "Real-time connection lost. Reconnecting..." — data still visible, polling fallback

### Real-time Behavior

WebSocket messages of type `EVENT_PUBLISHED` → add marker to map + prepend to event feed  
`EVENT_UPDATED` → update marker color/size if verification status changed  
`DWEG_PROPAGATION_ALERT` → show toast notification with link to event

---

## Screen 2 — Event Detail

### Purpose
Full intelligence view of a single canonical weather event.

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ ← Back to Map                                                    │
│                                                                   │
│ FLOODING · URBAN FLOOD                    Severity ●3   VERIFIED │
│ Chennai, Tamil Nadu                                               │
│ First reported: Sep 30, 12:00 · Last updated: 15 min ago         │
│ 8 evidence reports · Confidence 78%                              │
├──────────────────────┬────────────────────────────────────────────┤
│  MINI MAP (event     │  AI VERIFICATION PANEL                    │
│  centroid +          │  Status: VERIFIED                         │
│  evidence markers)   │  Score: 82%                               │
│                      │  "OpenWeatherMap confirms 85mm/h at..."    │
│                      │  ┌─ Evidence Items ─────────────────────┐ │
│                      │  │ ✓ Official API: 85mm/h (weight 0.15) │ │
│                      │  │ ✓ 6 nearby reports corroborate       │ │
│                      │  │ ✓ Source trust: 0.78                 │ │
│                      │  └───────────────────────────────────── ┘ │
├──────────────────────┴────────────────────────────────────────────┤
│  TABS: [Evidence Reports] [Media Gallery] [Event Timeline] [DWEG] │
├───────────────────────────────────────────────────────────────────┤
│  TAB CONTENT (below tabs)                                         │
└───────────────────────────────────────────────────────────────────┘
```

### Evidence Reports Tab

Table: `Source | Time | Location | Severity | Summary | Trust | Media`  
Each row expandable to show full AI extraction + raw text.

### Media Gallery Tab

Masonry grid of images/videos. Click to open lightbox. Image analysis results shown as overlaid tags ("Flooding evidence: 82%"). Face-blurred images show a notice.

### Event Timeline Tab

Vertical timeline (chronological): each evidence report as a node. Shows how severity evolved over time. Mini sparkline of severity trend.

### DWEG Tab

Split view:
- **Left:** Force-directed graph visualization (D3 or Cytoscape.js)
  - Nodes colored by type (event=blue, report=green, location=gray, official=purple)
  - Edges labeled with relationship type
  - Click node to see detail popover
- **Right:** Propagation Timeline + Evidence Chain narrative

### States

- **Loading:** Skeleton layout
- **Error:** "Failed to load event details. Retry" with retry button
- **Unverified event:** Banner "This event is UNVERIFIED. Evidence is being collected."
- **Contradicted event:** Red banner "AI analysis found contradicting evidence. Human review required."

---

## Screen 3 — Analytics

### Purpose
State and national-level weather intelligence statistics.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ANALYTICS                                   [Date Range Picker] │
│                                                                  │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                   │
│ │ 847    │ │ 4,213  │ │  23    │ │   8    │                   │
│ │Events  │ │Reports │ │ Active │ │Anomaly │                   │
│ └────────┘ └────────┘ └────────┘ └────────┘                   │
│                                                                  │
│ ┌──────────────────────┐ ┌─────────────────────────────────┐   │
│ │ Events by Category   │ │ Events Over Time (line chart)   │   │
│ │ (Donut chart)        │ │ Interval: [1h][6h][1d][7d]      │   │
│ └──────────────────────┘ └─────────────────────────────────┘   │
│                                                                  │
│ ┌──────────────────────┐ ┌─────────────────────────────────┐   │
│ │ India Choropleth Map │ │ Top States by Event Count       │   │
│ │ (events per state)   │ │ (Horizontal bar chart)          │   │
│ └──────────────────────┘ └─────────────────────────────────┘   │
│                                                                  │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ Source Distribution (stacked bar: API | Citizen | Feed)  │   │
│ └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Charts

All charts use Recharts. Colors from the design system palette (no random colors).  
Charts include:
- Event count by category: Donut
- Events over time: Line chart with category breakdowns
- India choropleth: MapLibre fill layer by state event count
- Source distribution: Stacked bar (API vs Citizen vs Feed vs Demo)
- Verification status breakdown: Stacked horizontal bar

### States

- **Loading:** Skeleton for each chart cell
- **Empty period:** "No events in selected period" in chart areas
- **Error:** Inline error with retry

---

## Screen 4 — Citizen Report Interface

### Purpose
Allow citizens to submit first-hand weather observations.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    REPORT WEATHER EVENT                          │
│                                                                  │
│  Step 1 of 4: What happened?                                    │
│  ────────────────────────────────                               │
│  Select event type:                                             │
│  [🌧 Rainfall] [⛈ Thunderstorm] [🌊 Flooding] [🌡 Heatwave]   │
│  [🌫 Fog] [🌪 Dust Storm] [💨 Strong Winds]                    │
│                                                                  │
│  How severe was it?                                             │
│  ○ Minor  ○ Moderate  ● Severe  ○ Extreme                      │
│                                                                  │
│  Describe what you observed:                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ text area                                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                         [Next →] │
└─────────────────────────────────────────────────────────────────┘
```

### Steps

1. **Event type + severity + description**
2. **Location:** Map with pin + GPS button + manual district/state dropdowns
3. **Media (optional):** Camera upload + gallery picker; preview with remove button
4. **Review + Submit:** Summary of all inputs, submit button

### GPS Flow

On Step 2: "Use My Location" button → browser geolocation API → map centers on user location → pin placed automatically → reverse geocoded to district/state shown below map → user can drag pin to adjust.

### Offline Support (PWA)

- Service worker caches the submit form
- If submission fails due to no connectivity: "Your report has been saved. It will be submitted when you're back online." — stored in IndexedDB
- When connectivity restored: report auto-submitted, user notified via browser notification

### Submission Confirmation

After submit:
```
┌────────────────────────────────────────────┐
│  ✓ Report Submitted                        │
│  Tracking ID: SP-2026-093042               │
│  Your report is being processed by AI.     │
│  You'll receive a notification when it's   │
│  reviewed.                                 │
│                          [View on Map →]   │
└────────────────────────────────────────────┘
```

### States

- **Submitting:** Button shows spinner, form inputs disabled
- **Offline:** Banner at top "You're offline. Report will be saved and submitted when connected."
- **Validation error:** Inline field-level error messages (red text below field)

---

## Screen 5 — Analyst Interface

### Purpose
Triage incoming reports, run verification, manage duplicate clusters.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ VERIFICATION QUEUE                            [Filter] [Sort ▼] │
│                                                                  │
│ ┌─────────────────────────────────────────────────────────┐    │
│ │ ⚠ REQUIRES REVIEW · FLOODING · Extreme                  │    │
│ │ Chennai, Tamil Nadu · 30 Sep 14:15 · 3 reports          │    │
│ │ AI: CONTRADICTED (0.28) · Source Trust: 0.45            │    │
│ │ [View Details] [Quick Verify ✓] [Quick Reject ✗]       │    │
│ └─────────────────────────────────────────────────────────┘    │
│ ...                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Event Detail (Analyst View)

Extends the public event detail with:

- **AI Recommendation Panel:** Recommended action (verify/reject/more-evidence) with confidence
- **Override Form:** Status selector + required reason text area + submit button
- **Duplicate Cluster Panel:** Shows all reports in cluster; "Split Cluster" and "Merge" actions
- **Source Trust Panel:** Trust score + historical accuracy chart for this source

### Duplicate Cluster Management

```
┌────────────────────────────────────────────────────────────┐
│ DUPLICATE CLUSTER (8 reports)              [Split] [Merge] │
│                                                             │
│ ☑ Rep-001 Citizen · Chennai · 12:00 · "knee deep water"   │
│ ☑ Rep-002 Citizen · Chennai · 12:15 · "flooding Adyar"    │
│ ☑ Rep-003 API     · Chennai · 13:30 · "85mm/h rainfall"   │
│ ☐ Rep-004 Citizen · Tambaram· 11:45 · "some rain"         │
│                                                             │
│ Rep-004 selected for split → [Confirm Split]               │
└────────────────────────────────────────────────────────────┘
```

### States

- **Queue empty:** "All caught up! No reports requiring review."
- **Loading queue:** Skeleton cards
- **Submitting override:** Button spinner, form locked

---

## Screen 6 — Admin Panel

### Purpose
Platform operations: users, connectors, health, moderation.

### Sub-screens

#### 6.1 System Health
```
┌──────────────────────────────────────────────────────────────┐
│ SYSTEM HEALTH                           Last checked: 30s ago │
│                                                               │
│ ● PostgreSQL    HEALTHY   │ ● Redis       HEALTHY            │
│ ● Kafka         HEALTHY   │ ● OpenSearch  HEALTHY            │
│ ● Neo4j         HEALTHY   │ ● AI Workers  HEALTHY (3/3 up)   │
│                                                               │
│ INGESTION RATE: 45 msg/min ────────────────────────────────  │
│ QUEUE DEPTH:    12 pending ▁▂▁▁▂▁▁▁▃▁▁▁▂▁                  │
│ ERROR RATE:     0.02/min                                      │
│                                                               │
│ CONNECTOR STATUS:                                             │
│ ● OpenWeatherMap   HEALTHY  142/hr   Last: 30s ago           │
│ ● Demo Connector   HEALTHY  520/hr   Last: 5s ago            │
│ ✗ IMD API          DOWN              Last error: timeout      │
└──────────────────────────────────────────────────────────────┘
```

#### 6.2 Connector Management

Table: `Name | Type | Status | Trust Score | Records/hr | Actions`  
Row actions: Enable/Disable toggle, Edit config (modal), View trust history  
Add Connector button → modal form

#### 6.3 User Management

Table: `Email | Name | Role | Active | Joined | Last Login | Actions`  
Actions: Change role (modal), Enable/Disable, Reset password  
Search by email/name

#### 6.4 Audit Log

Filterable table: `Timestamp | User | Action | Entity | Details`  
Detail column shows diff of old→new value on hover.

#### 6.5 Flagged Reports

Reports with `status=FLAGGED` (from AI safety detection). Actions: Dismiss flag, Delete report, Escalate.

---

## Screen 7 — DWEG Intelligence View

### Purpose
Dedicated view for the Dynamic Weather Evidence Graph innovation.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ DWEG: Flooding Event — Chennai [Sep 30]   [Back to Event]       │
├────────────────────────┬────────────────────────────────────────┤
│  GRAPH VISUALIZATION   │  EVIDENCE CHAIN                        │
│                        │                                        │
│  [D3 force-directed    │  "Flooding event first reported in     │
│   graph with nodes     │  Tambaram at 12:00 by anonymous        │
│   and edges]           │  citizen. Corroborated by 6 reports.   │
│                        │  OpenWeatherMap confirms 85mm/h..."    │
│  Legend:               │                                        │
│  ● Event               │  ─ Evidence Timeline ─                 │
│  ○ Report              │  12:00 · Rep-001 · Citizen · Tambaram  │
│  □ Location            │  12:15 · Rep-002 · Citizen · Chennai   │
│  ◇ Official            │  13:30 · Rep-003 · API · Chennai       │
│                        │  14:15 · Rep-007 · Citizen · Adyar     │
│  [Node count: 14]      │                                        │
├────────────────────────┴────────────────────────────────────────┤
│  CONFIDENCE FIELD MAP + PROPAGATION TIMELINE                    │
│                                                                  │
│  [India map with heatmap confidence overlay for this event]     │
│  [Timeline scrubber: play animation of propagation]             │
│                                                                  │
│  ◀ ▶  12:00 ─────────────────── 15:30                         │
│       [Tambaram]  [Chennai]  [Adyar] → [Tiruvallur?]           │
└─────────────────────────────────────────────────────────────────┘
```

### Graph Interaction

- **Hover node:** Tooltip showing node details
- **Click node:** Right panel updates to show node details
- **Click edge:** Tooltip showing relationship type and score
- **Zoom/pan:** Standard D3 zoom
- **Highlight path:** Click a report node → highlights the CORROBORATES edge to the event

### Propagation Animation

Timeline scrubber at bottom of map panel. Play button animates evidence markers appearing on the map in chronological order, with arrows showing propagation direction between districts.

### States

- **Loading graph:** Spinner in graph area with "Building evidence graph..."
- **Graph too large (>100 nodes):** Simplified view showing only primary nodes, with "Expand" option
- **Propagation still computing:** "Propagation analysis in progress..." badge
- **No propagation detected:** "Event appears localized to one area" message

---

## Filter Panel (Global)

Filters apply to the current view (map, events list, analytics). Filter state persists in URL query params.

### Filter Controls

| Filter | Control Type | Values |
|---|---|---|
| Date range | Date range picker | Custom or: Today, 7d, 30d, Custom |
| Event category | Multi-select chips | All 7 categories |
| State | Dropdown (India states list) | 28 states + UTs |
| District | Dependent dropdown | Based on selected state |
| Verification status | Multi-select chips | 5 status values |
| Severity | Slider range (1–4) | Min–max slider |
| Confidence | Slider range (0–1) | Min–max slider |
| Source | Multi-select | Dynamic list from `/api/v1/sources` |
| Show demo data | Toggle | On/Off |

Applied filters shown as chips below the filter panel with × to remove each.

---

## Real-time UX

### WebSocket Connection States

| State | UI Indicator |
|---|---|
| Connected | Green dot "● Live" in topbar |
| Connecting | Yellow dot "● Connecting..." |
| Disconnected | Red dot "● Offline — data may be stale" banner |

### Real-time Transitions

- New event marker: Appears on map with a 400ms scale-in animation
- Event feed card: Slides in from top with 300ms transition
- Metric counters: Animate to new value with 500ms counter transition
- Verification status change: Card border color transitions over 600ms

### Toast Notifications

- Position: Top-right corner
- Duration: 5 seconds auto-dismiss (click to persist)
- Types: `INFO` (blue), `SUCCESS` (green), `WARNING` (orange), `ERROR` (red)
- DWEG propagation alerts: Always orange, include "View Event" button

---

## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1280px) | Full sidebar + main layout as specified |
| Tablet (768–1280px) | Sidebar collapses to icons; map fills screen width |
| Mobile (<768px) | Sidebar hidden (hamburger menu); single column; map fills viewport; event feed becomes bottom sheet |

Map-first on mobile: map fills screen, filters and event feed accessible via FAB button and bottom sheet.

---

## Accessibility

- All interactive elements have focus indicators
- Color is never the only encoding (verification status also uses icon + text)
- All map markers have `aria-label` describing the event
- Charts include accessible data tables as alternative
- Keyboard navigation through all primary flows

---

## Loading and Empty States Summary

| Screen | Loading | Empty | Error |
|---|---|---|---|
| Live Map | Skeleton markers + spinner | "No events in period" map overlay | "Connection failed" banner |
| Event Detail | Skeleton layout | — | "Event not found" / retry |
| Analytics | Chart skeletons | "No data for period" per chart | Inline retry per chart |
| Citizen Report | — | — | Field-level validation; submission error toast |
| Analyst Queue | Skeleton cards | "All caught up!" | Reload prompt |
| Admin Health | Skeleton grid | — | Status indicators show UNKNOWN |
| DWEG View | Graph spinner | "No evidence graph for this event" | Graph render error + retry |
