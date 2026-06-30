# Odoo Forecourt Management System (FMS)
## Comprehensive Implementation Guide — Shell Maanzoni Service Station

**Version:** 1.0.0 (ported from ERPNext FMS Guide v3.0.0)
**Platform:** Odoo 17 / 18 (Community or Enterprise)
**Station Reference:** Shell Maanzoni Service Station (Anika Global Limited)
**Network:** Shell Kenya Limited — Multi-Site
**Currency:** KES
**Last Updated:** June 2026

---

## Table of Contents

1. [Introduction & Business Context](#1-introduction--business-context)
2. [The Golden Rules](#2-the-golden-rules)
3. [The Three Meter Types — Core Concept](#3-the-three-meter-types--core-concept)
4. [Cross-Validation](#4-cross-validation)
5. [Architecture Overview](#5-architecture-overview)
6. [Odoo Foundation Setup](#6-odoo-foundation-setup)
7. [Data Model — Complete Model Reference](#7-data-model--complete-model-reference)
8. [Extending Native Odoo Models](#8-extending-native-odoo-models)
9. [Manual Station Workflows](#9-manual-station-workflows)
10. [PTS Controller Integration](#10-pts-controller-integration)
11. [Shift Lifecycle & Cash Reconciliation](#11-shift-lifecycle--cash-reconciliation)
12. [Fuel Delivery (Receipt) Workflow](#12-fuel-delivery-receipt-workflow)
13. [Wetstock Reconciliation](#13-wetstock-reconciliation)
14. [Fleet Cards & Credit Customers](#14-fleet-cards--credit-customers)
15. [Kenya Compliance](#15-kenya-compliance)
16. [Security & Data Isolation](#16-security--data-isolation)
17. [Offline Resilience & Error Handling](#17-offline-resilience--error-handling)
18. [Server Infrastructure & DevOps](#18-server-infrastructure--devops)
19. [Implementation Phases](#19-implementation-phases)
20. [Testing & Quality Assurance](#20-testing--quality-assurance)
21. [Known Limitations](#21-known-limitations)
22. [Appendix](#22-appendix)
23. [Architectural Principle — Shift as Metadata](#23-architectural-principle--shift-as-metadata)
24. [Standard Odoo Integration Patterns](#24-standard-odoo-integration-patterns)
25. [Shift Auto-Open and Carry-Forward Logic](#25-shift-auto-open-and-carry-forward-logic)
26. [HQ Configuration Powers](#26-hq-configuration-powers)
27. [Reporting Suite](#27-reporting-suite)
28. [HQ Dashboard](#28-hq-dashboard)
29. [Backend Menus & Dashboards](#29-backend-menus--dashboards)
30. [Glossary of ERPNext → Odoo Term Mapping](#30-glossary-of-erpnext--odoo-term-mapping)

---

## 1. Introduction & Business Context

### 1.1 What Problem Are We Actually Solving?

A petrol station appears simple — buy fuel, sell fuel. Three silent problems can destroy a station financially before management notices.

**Problem 1 — Cash Leakage.** On 17-05-2026 at Shell Maanzoni, cashier Swedi Abuti had expected cash of KES 14,300.70 but declared KES 13,200.00 — a KES 1,100.70 shortage on one shift. Across five cashiers that same shift the total over/under was (KES 983.43). Without a system that reconciles cash collected against fuel dispensed per cashier per shift, these shortfalls remain invisible in aggregate and are never traced to source.

**Problem 2 — Fuel Losses.** With 2,658.43 litres sold on the shift shown (KES 619,312.14 value: Unleaded Extra 955.99 L @ KES 204,785.65 + Diesel Extra 1,702.44 L @ KES 414,526.49), even a 0.3% wetstock loss is 8 litres — KES 1,900 per shift. Annualised: over KES 690,000 in unexplained stock shrinkage.

**Problem 3 — Delivery Fraud.** The supplier docket says 8,000 litres. The before/after dip says 7,796 litres arrived. Without both dip readings, you cannot dispute the docket and the KES 30,600 shortfall goes unrecovered.

### 1.2 The Legacy System: What It Does Well

The existing system already captures all three meter types per nozzle — the `Elect(Cash)`, `Elec(Ltrs)`, and `Man(Ltrs)` columns are visible in the live screen. It also produces a per-cashier Daily Shift Cash Reconciliation Sheet with Invoices, POS, VISA, Receipts, Payments, Expected Cash, Actual Cash, and Over/Under columns per cashier row — exactly the level of accountability needed.

The Odoo FMS will:
- Replicate the three-meter capture and the per-cashier reconciliation sheet exactly
- Add the wetstock reconciliation (theoretical vs actual dip) that the legacy system handles manually
- Add automated journal entries (`account.move`) that the legacy system never produces
- Add PTS controller integration for partially automated data capture
- Add EPRA and KRA eTIMS compliance

### 1.3 Real Data Reference — Shell Maanzoni

All examples in this guide use actual Shell Maanzoni data (unchanged from the legacy reference set).

**Station configuration:**

| Element | Detail |
|---|---|
| Products | Unleaded Extra (UX), V-Power (VP), Diesel Extra (DX) |
| EPRA Prices (May 2026) | UX: KES 214.20/L, VP: KES 229.00/L, DX: KES 242.90/L |
| Tanks | T1 (V-Power), T2 (Unleaded), T3 (Diesel) |
| Islands | 4 islands; pumps named UX/DX/VP with island suffix |
| Typical shift | ~2,658 litres, ~KES 619,000 revenue |
| Cashiers per shift | 4–5 cashiers plus supervisor/manager row |

**Observed meter variances from live legacy screen (Elec Vol vs Man Mech):**

| Pump | Elec Ltrs | Man Ltrs | Var (Ltrs) | Var % |
|---|---|---|---|---|
| U5 (Island 3 UX) | 80.99 | 81.00 | −0.00 | 0.01% |
| U6 (Island 3 UX) | 320.56 | 321.00 | −0.43 | 0.13% |
| L5 (Island 3 DX) | 50.24 | 50.00 | +0.23 | **0.46%** → approaching warning |
| L6 (Island 3 DX) | 212.04 | 212.00 | +0.04 | 0.02% |
| U7 (Island 4 UX) | 80.53 | 80.00 | +0.52 | 0.65% → **Warning** |
| U8 (Island 4 UX) | 349.65 | 349.00 | +0.65 | 0.19% |
| L7 (Island 4 DX) | 304.11 | 304.00 | +0.11 | 0.04% |
| L8 (Island 4 DX) | 214.49 | 215.00 | −0.51 | 0.24% |

> Note: U7 at 0.65% exceeds the 0.50% Check B fail threshold. In the Odoo system this is flagged as **Fail** and blocks shift close until an Amendment reading or pump inspection is logged.

**Cash reconciliation data — 17-05-2026:**

| Cashier | Sales | Invoices | POS | VISA | Total Credits | Recpts | Pymts | Expected Cash | Actual Cash | Over/(Under) |
|---|---|---|---|---|---|---|---|---|---|---|
| SWEDI ABUTI | 219,118.70 | 175,168.00 | 5,000.00 | 20,700.00 | 200,868.00 | (1,000.00) | 2,950.00 | 14,300.70 | 13,200.00 | **(1,100.70)** |
| JOEL MUSEMBI | 250.00 | — | — | — | — | 0.00 | — | 250.00 | 250.00 | — |
| ABDIRAHMAN AHM | — | — | — | — | — | 0.00 | 129,295.00 | (129,295.00) | (129,295.00) | — |
| PETER MBEVE | 149,724.50 | 124,021.00 | — | 12,110.00 | 136,131.00 | 0.00 | 410.00 | 13,183.50 | 13,300.00 | **116.50** |
| JOSEPH MATALE | 252,498.23 | 238,349.00 | 11,500.00 | 1,000.00 | 250,849.00 | 0.00 | — | 1,649.23 | 1,650.00 | **0.77** |
| **TOTAL** | **621,591.43** | **537,538.00** | **16,500.00** | **33,810.00** | **587,848.00** | **(1,000.00)** | **132,465.00** | **(99,911.57)** | **(100,895.00)** | **(983.43)** |

> ABDIRAHMAN AHM row represents the manager/supervisor float pool — large Pymts out = safe deposits or float redistribution. The negative Expected Cash in this row is by design (supervisor holds no till; they receive cash from cashiers and deposit to safe).

### 1.4 Terminology

| Term | Definition |
|---|---|
| **ATG** | Automatic Tank Gauge |
| **DX** | Diesel Extra — AGO grade at Shell Maanzoni |
| **Elec Cash** | Electronic Cash meter — cumulative KES totalizer on pump display |
| **Elec Vol** | Electronic Volume meter — cumulative litre totalizer on pump display |
| **EPRA** | Energy & Petroleum Regulatory Authority (Kenya) |
| **eTIMS** | Electronic Tax Invoice Management System (KRA) |
| **FMS** | Forecourt Management System — the custom Odoo module(s) |
| **GRN / Receipt** | Goods Received Note — modelled in Odoo as a `stock.picking` (incoming) generated from a `purchase.order` |
| **Island** | Physical forecourt position grouping pump units |
| **jsonPTS** | Technotrade PTS-2 proprietary JSON protocol |
| **Man Mech** | Manual Mechanical — physical number wheels on pump body |
| **PMS / UX / VP** | Premium Motor Spirit; UX = Unleaded Extra, VP = V-Power |
| **PTS-2** | Technotrade LLC forecourt controller |
| **RTT** | Return to Tank — volume dispensed back to tank during testing |
| **Shift** | A defined operating period; one accountability contract per cashier |
| **Totalizer** | Non-resettable cumulative counter in each pump |
| **UX** | Unleaded Extra — standard petrol grade at Shell Maanzoni |
| **VP** | V-Power — premium petrol grade at Shell Maanzoni |
| **AVCO** | Average Cost — Odoo's costing method, equivalent to ERPNext's WAC |
| **Wetstock** | Fuel stored in underground tanks |

---

## 2. The Golden Rules

Every model, every field, every constraint exists to enforce one of these rules.

**Rule 1 — The Shift Is the Unit of Everything.** A shift is a bounded accountability contract. Every litre dispensed, every shilling collected, every delivery, every dip — all belongs to a shift.

**Rule 2 — Three Meters, One Truth.** Every modern dispensing pump has three independent measurement systems. All three must be read at open and close. Divergence between them is either a data entry error or evidence of tampering.

**Rule 3 — Dip Readings Are the Tank's Bank Statement.** A dip reading measures physical fuel independently of pump meters. It catches meter drift, unrecorded sales, theft, and leaks.

**Rule 4 — Cash and Fuel Reconcile Separately.** Cash: did each cashier collect the right amount? Wetstock: did the right volume leave the tanks? Computed independently; never merged.

**Rule 5 — No Opening Reading, No Sales.** Sales cannot begin before all three opening meter readings are captured per nozzle.

**Rule 6 — Deliveries Need Before and After Dips.** Never accept a delivery on docket volume alone.

**Rule 7 — Dual Control on All Cash Movements.** Float, pickup, safe drop — two people, two user accounts, every time.

**Rule 8 — Each Cashier Reconciles Independently.** The cash formula runs per `fms.cashier.session`, matching the current paper reconciliation sheet row by row.

---

## 3. The Three Meter Types — Core Concept

This is the foundation of all wetstock integrity and fraud detection. The legacy system already captures all three types. The Odoo system replicates this exactly.

### 3.1 Physical Layout

```
┌────────────────────────────────────────────────────────┐
│                    DISPENSING PUMP                      │
│                                                         │
│  ┌──────────────────┐   ┌────────────────────────┐     │
│  │  DIGITAL DISPLAY  │   │  MECHANICAL DRUMS       │     │
│  │  Vol: 171,275,183 │   │  (Physical Number Wheels│     │
│  │  Cash: 29,387,277 │   │   — no power needed)    │     │
│  └──────────────────┘   └────────────────────────┘     │
│   Electronic Vol + Cash    Manual Mechanical             │
└────────────────────────────────────────────────────────┘
```

### 3.2 Type 1 — Electronic Volume (Elec Vol)

Cumulative digital counter: total litres dispensed since installation. The primary legal measurement.

- Counts forward only; never resets; sealed by Weights & Measures
- 3 decimal places: e.g. 171,275,183.070 (actual UX8 totalizer at Shell Maanzoni)
- Primary figure used in all wetstock and sales calculations

`Elec Vol Sold = Closing Elec Vol − Opening Elec Vol`

### 3.3 Type 2 — Electronic Cash (Elec Cash)

Cumulative KES value of fuel dispensed — mathematically linked to Elec Vol via the programmed EPRA price.

`Elec Cash Sold = Closing Elec Cash − Opening Elec Cash`

**Cross-check (same-rate shift):**
```
Expected Cash = Elec Vol Sold × EPRA Rate
Discrepancy = |Elec Cash Sold − Expected Cash|

Shell Maanzoni 17-05-2026 example:
  U7 Island 4: 80.53 L × 214.20 = KES 17,249.63 expected
               Legacy shows KES 17,248.46 → discrepancy KES 1.17 → Pass ✓
  U8 Island 4: 349.65 L × 214.20 = KES 74,895.03 expected
               Legacy shows KES 74,895.24 → discrepancy KES 0.21 → Pass ✓
```

Why store this if we can compute it? Because it is a **physically independent sensor inside the pump**. If someone miskeys the Elec Vol reading, the Cash meter immediately exposes the discrepancy.

### 3.4 Type 3 — Manual Mechanical (Man Mech)

Physical odometer-style counter — rotating drums driven by the flow mechanism. Completely independent of electronics; requires no power; cannot be reset without a KEBS physical key.

Less precise (0.1 L vs 0.001 L for electronic), but immune to electronic tampering. Last line of defence when tampering is suspected.

`Mech Vol Sold = Closing Man Mech − Opening Man Mech`
Must be within 0.5% of Elec Vol Sold. Above 1.0%: lock pump, notify KEBS.

### 3.5 Summary Table

| Attribute | Elec Vol | Elec Cash | Man Mech |
|---|---|---|---|
| Display | Digital screen | Digital screen | Physical number wheels |
| Unit | Litres | KES | Litres |
| Precision | 0.001 L | KES 0.01 | 0.1 L |
| Power required | Yes | Yes | No |
| Primary use | Volume sold | Cash cross-check | Tampering detection |

---

## 4. Cross-Validation

### 4.1 The Four-Way Check

At shift close, four independent data sources must agree about how much fuel was sold:

```
                   ┌────────────────────┐
                   │   DIP READING (L)  │  ← Physical reality in tank
                   └─────────┬──────────┘
                             │ must agree with
             ┌───────────────┼───────────────┐
   ┌──────────▼──┐  ┌─────────▼────┐  ┌──────▼──────────┐
   │ Elec Vol    │  │ Elec Cash    │  │ Man Mech        │
   │ (L)         │  │ ÷ Rate = (L) │  │ (L)             │
   └─────────────┘  └──────────────┘  └─────────────────┘
         └────────────────┴────────────────────┘
                  All must agree within tolerance
```

### 4.2 Check A — Volume vs Cash (per nozzle)

```python
discrepancy = abs(elec_cash_sold - (elec_vol_sold * shift_rate))
# Pass: ≤ KES 5    Warning: KES 5–20    Fail: > KES 20
```

### 4.3 Check B — Volume vs Mechanical (per nozzle)

```python
divergence_pct = abs(elec_vol_sold - mech_vol_sold) / elec_vol_sold * 100
# Pass: ≤ 0.30%   Warning: 0.30–0.50%   Fail: 0.50–1.00%   Critical > 1.00% → lock pump
```

**Applying this to the live Shell Maanzoni data:**

| Pump | Elec | Mech | Divergence | Status |
|---|---|---|---|---|
| U7 | 80.53 | 80.00 | 0.65% | **Fail** — requires Amendment or inspection |
| L5 | 50.24 | 50.00 | 0.48% | **Warning** — schedule calibration |
| U8 | 349.65 | 349.00 | 0.19% | Pass ✓ |
| L8 | 214.49 | 215.00 | 0.24% | Pass ✓ |

### 4.4 Check D — Tank Wetstock

```
Theoretical Closing = Opening Dip + Deliveries − Tank Elec Vol Sold
Wetstock Variance   = Theoretical − Actual Closing Dip
```

### 4.5 Check E — Elec Cash vs POS Order Lines (per shift)

```
Σ pos.order.line amounts per nozzle ≈ Elec Cash Sold per nozzle
Tolerance: ≤ KES 10.00 per nozzle
```

---

## 5. Architecture Overview

### 5.1 Design Principles

1. One source of truth per concept — shift date on `fms.shift`; not repeated on children.
2. Three meter types, one model — `meter_type` is a selection field, not separate models.
3. Per-cashier accountability — cash formula runs per `fms.cashier.session`, not per shift.
4. Extend native Odoo models, never replace — FMS adds fields and inherited methods to `stock.picking`, `pos.order`, `stock.move`.
5. `company_id` on every FMS model — Odoo's standard multi-company record rules cascade automatically.
6. Odoo addon module (`fms`) hosts all custom models, views, security, and the PTS integration controllers — installed alongside Odoo's `stock`, `point_of_sale`, `account`, and `hr` apps.

### 5.2 Architecture

```
┌──────────────── Shell Kenya HQ ─────────────────────┐
│   Odoo Web Client — full cross-company visibility     │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │      Odoo Application Server│
         │  Odoo Core Apps + fms addon │
         └─────────────┬──────────────┘
                       │
         ┌─────────────┼──────────────┐
  ┌──────▼──────┐ ┌────▼──────┐ ┌────▼──────────┐
  │ PTS-2 Site  │ │Generic PTS│ │ Manual Site   │
  │ (jsonPTS)   │ │ (RS-485)  │ │ (no ATG/PTS)  │
  └─────────────┘ └───────────┘ └───────────────┘
```

### 5.3 Technology Stack

| Layer | Technology |
|---|---|
| ERP Platform | Odoo 17 / 18 Community or Enterprise |
| Language | Python 3.10+ |
| Database | PostgreSQL 14+ |
| Background Jobs | `ir.cron` (built-in scheduler); `queue_job` (OCA) for heavy async work |
| Serial / Modbus | pySerial 3.5+, pymodbus 3.x (run as a companion gateway process, not inside the Odoo worker) |
| PTS-2 Protocol | jsonPTS over HTTPS + WebSocket (RFC 6455) terminated by a small FastAPI/Flask bridge service that calls Odoo's external API (JSON-RPC/XML-RPC or REST controllers) |
| Real-time push to UI | Odoo `bus.bus` (longpolling) or `bus.bus` + websockets (Odoo 17+ native worker) |

> **Note on PTS-2 ↔ Odoo coupling.** Odoo does not run a native always-on WebSocket *server* for arbitrary external protocols the way Frappe's `frappe.ws` does. The recommended pattern (detailed in §10) is a thin **PTS Bridge** service (Python, stateless, can live in the same addon as a long-running script or as a tiny sidecar container) that terminates the PTS-2's HTTP push and WebSocket connections, then writes into Odoo via `odoorpc`/`xmlrpc` calls or directly via Odoo's HTTP `@http.route` controllers exposed by the `fms` module. Both options are documented in §10; the HTTP-controller option is recommended because it keeps everything inside one Odoo addon and one deployable.

---

## 6. Odoo Foundation Setup

### 6.1 Company Hierarchy

Odoo multi-company is flat with a `parent_id` field on `res.company` (no deep hierarchy requirement, but parent/child is supported):

```
Shell Kenya Limited                (res.company, parent)
├── Shell Maanzoni (Anika Global)  (res.company, child)
├── Shell Mombasa Road             (res.company, child)
└── Shell Westlands                (res.company, child)
```

Each station is a separate `res.company` record with `parent_id = Shell Kenya Limited`. Users at HQ get access to all companies via `Settings → Users → Multi-Company`; station users are restricted to their own company.

### 6.2 Chart of Accounts

Odoo's Chart of Accounts is per-company (`account.account`, scoped by `company_id`). Use Odoo's **Fiscal Localization** for Kenya as the base, then add the following:

**Income**

| Account | Purpose |
|---|---|
| Fuel Sales — PMS Unleaded (UX) | Unleaded Extra revenue |
| Fuel Sales — PMS V-Power (VP) | V-Power revenue (separate — different EPRA price) |
| Fuel Sales — AGO Diesel (DX) | Diesel Extra revenue |
| Fuel Sales — DPK | Kerosene revenue |

**COGS / Expense**

| Account | Purpose |
|---|---|
| COGS — Fuel PMS Unleaded | Cost of UX sold |
| COGS — Fuel PMS V-Power | Cost of VP sold |
| COGS — Fuel AGO Diesel | Cost of DX sold |
| Wetstock Variance — PMS | Petrol losses |
| Wetstock Variance — AGO | Diesel losses |
| Cash Short / Over | Cashier variances (per-cashier posting) |
| Drive-Off Losses | Fuel dispensed, not paid |

**Assets**

| Account | Purpose |
|---|---|
| Fuel Inventory — PMS Unleaded | Physical UX in Tank 2 (Odoo stock valuation account on the product category) |
| Fuel Inventory — PMS V-Power | Physical VP in Tank 1 |
| Fuel Inventory — AGO Diesel | Physical DX in Tank 3 |
| MPesa Clearing | MPesa collections |
| Card Payment Clearing | VISA/card settlements |
| Fleet Card Clearing | Shell/fleet card |
| Safe — Main | Site safe balance |
| Till — Active | Active cashier till (maps to the POS **Cash** payment method's `journal_id` outstanding account) |

### 6.3 Fuel Grade Products

> **Critical:** Keep V-Power and Unleaded as **separate `product.product` records** — different EPRA price schedule, different revenue accounts (via `product.category` / income account override), potentially different average cost from different depot batches.

| Field | FUEL-PMS-UNL | FUEL-PMS-VP | FUEL-AGO |
|---|---|---|---|
| Internal Reference | `FUEL-PMS-UNL` | `FUEL-PMS-VP` | `FUEL-AGO` |
| Unit of Measure | Litre (custom UoM, category "Volume") | Litre | Litre |
| Product Type | Storable Product | Storable Product | Storable Product |
| Costing Method | Average Cost (AVCO) | Average Cost (AVCO) | Average Cost (AVCO) |
| Sales Price | 214.20 | 229.00 | 242.90 |
| Default route / warehouse | Tank 2 — Unleaded | Tank 1 — V-Power | Tank 3 — Diesel |

**Why AVCO?** Each delivery arrives at a slightly different cost. Average Cost blends automatically on every receipt. This is the only correct valuation method for bulk liquid fuel — equivalent to ERPNext's WAC, configured per product category under `Inventory Valuation = Automated`, `Costing Method = Average Cost (AVCO)`.

**Custom fields on `product.template`** (added by the `fms` module):

```python
class ProductTemplate(models.Model):
    _inherit = "product.template"

    fms_is_fuel_product = fields.Boolean(string="Is Fuel Product")
    fms_fuel_grade = fields.Selection([
        ("UX", "Unleaded Extra"),
        ("VP", "V-Power"),
        ("DX", "Diesel Extra"),
        ("DPK", "Kerosene"),
    ], string="Fuel Grade")
```

### 6.4 Tank Locations — Shell Maanzoni

Odoo models tanks as `stock.location` records of usage type **Internal**, nested under the station's stock warehouse view location. This is more natural in Odoo than ERPNext's "Warehouse-as-tank" pattern, since Odoo already distinguishes Warehouse (a logistics concept) from Location (a physical bin/area within it).

```
Shell Maanzoni Forecourt (stock.warehouse)
└── Shell Maanzoni Forecourt/Stock (view location)
    ├── Tank 1 — V-Power   (stock.location, usage=internal)
    ├── Tank 2 — Unleaded  (stock.location, usage=internal)
    └── Tank 3 — Diesel    (stock.location, usage=internal)
```

| Location | Product | Nozzle type on pumps |
|---|---|---|
| Tank 1 — V-Power | FUEL-PMS-VP | VP / P nozzles |
| Tank 2 — Unleaded | FUEL-PMS-UNL | UX / U nozzles |
| Tank 3 — Diesel | FUEL-AGO | DX / L nozzles |

**Custom fields on `stock.location`:**

```python
class StockLocation(models.Model):
    _inherit = "stock.location"

    fms_is_fuel_tank = fields.Boolean(string="Is Fuel Tank")
    fms_capacity_litres = fields.Float(string="Capacity (L)")
    fms_pts2_tank_number = fields.Integer(string="PTS-2 Tank Number")
    fms_fuel_product_id = fields.Many2one("product.product", string="Fuel Product")
```

### 6.5 User Roles → Odoo Security Groups

Odoo's permission unit is the **Security Group** (`res.groups`), combined with **Record Rules** (`ir.rule`) for row-level (company/owner) filtering.

| Role | Odoo Group (`fms.group_*`) | Permissions |
|---|---|---|
| Shell HQ Manager | `fms.group_hq_manager` | Read/Write all companies; configuration rights |
| Shell HQ Auditor | `fms.group_hq_auditor` | Read-only, all companies |
| Site Manager | `fms.group_site_manager` | Full access; own company; approve variances; post journal entries |
| Site Supervisor | `fms.group_site_supervisor` | Open/close shifts; authorise cash events; own company |
| Site Cashier | `fms.group_site_cashier` | Own sessions, POS, cash events; own company |
| Pump Attendant | `fms.group_pump_attendant` | Meter readings, dip readings; own company |

### 6.6 Multi-Company Record Rules

Odoo applies company filtering automatically to most stock/sales/account models via the built-in **Multi-Company Rules** once a user is restricted to a list of `company_ids`. For FMS's own custom models, add an explicit rule:

```xml
<record id="fms_shift_company_rule" model="ir.rule">
    <field name="name">FMS Shift: multi-company</field>
    <field name="model_id" ref="model_fms_shift"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>
```

HQ Manager and HQ Auditor groups are simply granted access to *all* companies in their user record (`Settings → Users → Allowed Companies`); no restricting rule is added for them — unrestricted access is the absence of a restriction, same principle as ERPNext's User Permission model.

### 6.7 Forecourt Site Preferences (Settings Model)

Per-station configuration so variance thresholds and account names are configurable without touching Python. Modelled as a normal `fms.site.preferences` record (one per `company_id`), surfaced through Odoo's standard `res.config.settings` pattern for a friendly Settings-screen UX, or simply as a list view filtered by company for HQ.

```python
class FmsSitePreferences(models.Model):
    _name = "fms.site.preferences"
    _description = "Forecourt Site Preferences"

    company_id = fields.Many2one("res.company", required=True, index=True)
    default_fuel_supplier_id = fields.Many2one("res.partner")
    wetstock_normal_pct = fields.Float(default=0.30)
    wetstock_elevated_pct = fields.Float(default=0.50)
    cash_normal_kes = fields.Float(default=50.0)
    cash_elevated_kes = fields.Float(default=200.0)
    meter_check_a_warn_kes = fields.Float(default=5.0)
    meter_check_b_warn_pct = fields.Float(default=0.30)
    meter_check_b_fail_pct = fields.Float(default=0.50)
    meter_check_b_tamper_pct = fields.Float(default=1.00)
    cash_pickup_threshold = fields.Float(default=30000.0)
    min_settle_minutes = fields.Integer(default=10)
    send_daily_summary = fields.Boolean(default=True)
    report_recipient_ids = fields.Many2many("res.partner")
    # Account-name overrides
    till_active_account_id = fields.Many2one("account.account")
    safe_main_account_id = fields.Many2one("account.account")
    mpesa_clearing_account_id = fields.Many2one("account.account")
    card_clearing_account_id = fields.Many2one("account.account")
    cash_short_over_account_id = fields.Many2one("account.account")
    drive_off_losses_account_id = fields.Many2one("account.account")

    _sql_constraints = [
        ("company_uniq", "unique(company_id)", "Only one preferences record per company."),
    ]
```

---

## 7. Data Model — Complete Model Reference

### 7.1 Entity Relationship Diagram

```
fms.island ──< fms.pump ──< fms.pump.nozzle (one2many)
                               │
                               │ draws from (nozzle.tank_location_id)
                               ▼
stock.location (tank) ←──── fms.tank.dip.reading
                                    │
fms.shift (master) ──────────────────┼──────────────────────────┐
    │                               │ (reconcile)                │
    ├── fms.meter.reading           ▼                            │
    │   (3 types ×            fms.tank.wetstock.line             │
    │    open+close)                                            Forecourt
    ├── fms.cash.event ──── fms.cashier.session ───────────────── Transaction
    └── fms.fuel.delivery.dip → purchase.order / stock.picking    (PTS)
              │
              └──────────────────► fms.shift.reconciliation
                                          │
                                    Per-Cashier Summaries (one2many)
                                    Per-Tank Summaries (one2many)
                                    Nozzle MVR Summaries (one2many)
                                          │
                                    account.move (journal entry)
```

### 7.2 Addon Module File Structure

```
odoo/addons/fms/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── pts2.py                  ← PTS-2 HTTP receiver (@http.route)
│   ├── pts2_ws.py                ← WebSocket-style channel via Odoo bus, or bridge endpoint
│   └── offline_buffer.py
├── models/
│   ├── __init__.py
│   ├── fms_shift.py
│   ├── fms_meter_reading.py
│   ├── fms_meter_validation_result.py
│   ├── fms_tank_dip_reading.py
│   ├── fms_tank_calibration_chart.py
│   ├── fms_forecourt_transaction.py     ← PTS staging model
│   ├── fms_pump.py
│   ├── fms_pump_nozzle.py
│   ├── fms_pump_configuration.py        ← Hardware ID → Odoo pump mapping
│   ├── fms_cashier_session.py
│   ├── fms_cash_event.py
│   ├── fms_fuel_delivery_dip.py
│   ├── fms_shift_reconciliation.py
│   ├── fms_drive_off_record.py
│   ├── fms_fleet_card.py
│   ├── fms_forecourt_alert.py
│   ├── fms_pts2_device.py
│   ├── fms_site_preferences.py
│   ├── res_company.py                   ← territory/region helpers
│   ├── product_template.py              ← fms_* fields
│   ├── stock_location.py                ← fms_* tank fields
│   ├── stock_picking.py                 ← delivery dip linkage overrides
│   ├── pos_order.py                     ← fms_shift / fms_pump overrides
│   ├── account_move.py                  ← fms_shift linkage overrides
│   └── hr_employee.py                   ← fms_* cashier/RFID fields
├── wizards/
│   ├── fms_bulk_price_update_wizard.py
│   └── fms_close_shift_wizard.py
├── report/
│   ├── fms_daily_shift_summary.py       ← report.fms.daily_shift_summary (Python model)
│   ├── fms_cashier_reconciliation.py
│   ├── fms_wetstock_variance_trend.py
│   ├── fms_meter_discrepancy_log.py
│   └── fms_delivery_reconciliation.py
├── data/
│   ├── ir_cron_data.xml
│   ├── fms_security_groups.xml
│   └── mail_template_data.xml
├── security/
│   ├── ir.model.access.csv
│   └── fms_security_rules.xml
├── views/
│   ├── fms_shift_views.xml
│   ├── fms_meter_reading_views.xml
│   ├── fms_tank_dip_reading_views.xml
│   ├── fms_cashier_session_views.xml
│   ├── fms_shift_reconciliation_views.xml
│   ├── fms_dashboard_views.xml
│   └── fms_menus.xml
├── tests/
│   ├── __init__.py
│   ├── test_meter_validation.py
│   └── test_wetstock.py
└── static/
    └── src/
        └── js/  (optional OWL dashboard widgets)
```

`__manifest__.py` excerpt:

```python
{
    "name": "Forecourt Management System (FMS)",
    "version": "17.0.1.0.0",
    "depends": ["stock", "point_of_sale", "account", "hr", "purchase", "sale"],
    "data": [
        "security/fms_security_rules.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/fms_shift_views.xml",
        "views/fms_meter_reading_views.xml",
        "views/fms_tank_dip_reading_views.xml",
        "views/fms_cashier_session_views.xml",
        "views/fms_shift_reconciliation_views.xml",
        "views/fms_dashboard_views.xml",
        "views/fms_menus.xml",
    ],
    "installable": True,
    "application": True,
}
```

### 7.3 `fms.shift` (Master Record)

**Status state machine — new `readings_captured` state gates the shift:**

```
draft → open → readings_captured → closing → closed
                      ↓                ↓
                  disputed ←──────────→ closing  (manager re-opens)
```

`readings_captured` means all three opening meter readings for all active nozzles have been submitted. Without it, a shift cannot move to `closing` with incomplete readings.

```python
from odoo import models, fields, api
from odoo.exceptions import ValidationError

ALLOWED_TRANSITIONS = {
    "draft":             {"open"},
    "open":              {"readings_captured", "disputed"},
    "readings_captured": {"closing", "disputed"},
    "closing":           {"closed", "disputed"},
    "closed":            set(),
    "disputed":          {"closing"},
}

class FmsShift(models.Model):
    _name = "fms.shift"
    _description = "Forecourt Shift"
    _order = "opened_at desc"

    name = fields.Char(default="New", copy=False)
    company_id = fields.Many2one("res.company", required=True,
                                  default=lambda s: s.env.company)
    station_id = fields.Many2one("res.company", string="Station", required=True)
    shift_date = fields.Date(required=True, default=fields.Date.context_today)
    shift_label = fields.Selection([("day", "Day"), ("evening", "Evening"),
                                     ("night", "Night")], required=True)
    status = fields.Selection([
        ("draft", "Draft"), ("open", "Open"),
        ("readings_captured", "Readings Captured"),
        ("closing", "Closing"), ("closed", "Closed"), ("disputed", "Disputed"),
    ], default="draft", tracking=True)
    opened_at = fields.Datetime()
    closed_at = fields.Datetime()
    cashier_id = fields.Many2one("hr.employee", string="Primary Cashier")
    supervisor_id = fields.Many2one("hr.employee")
    float_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="company_id.currency_id")
    rate_pms_unl = fields.Monetary(currency_field="currency_id")
    rate_pms_vp = fields.Monetary(currency_field="currency_id")
    rate_ago = fields.Monetary(currency_field="currency_id")
    rate_dpk = fields.Monetary(currency_field="currency_id")
    meter_validation_ok = fields.Boolean(readonly=True)
    journal_entry_id = fields.Many2one("account.move", readonly=True)
    reconciliation_notes = fields.Text()

    meter_reading_ids = fields.One2many("fms.meter.reading", "shift_id")
    dip_reading_ids = fields.One2many("fms.tank.dip.reading", "shift_id")
    cashier_session_ids = fields.One2many("fms.cashier.session", "shift_id")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("fms.shift") or "New"
        return super().create(vals_list)

    @api.constrains("cashier_id", "supervisor_id")
    def _check_distinct_people(self):
        for rec in self:
            if rec.cashier_id and rec.supervisor_id and rec.cashier_id == rec.supervisor_id:
                raise ValidationError("Cashier and Supervisor must be different employees.")

    @api.constrains("status", "station_id")
    def _check_single_open_shift(self):
        for rec in self:
            if rec.status in ("open", "closing"):
                conflict = self.search([
                    ("station_id", "=", rec.station_id.id),
                    ("status", "in", ("open", "closing")),
                    ("id", "!=", rec.id),
                ], limit=1)
                if conflict:
                    raise ValidationError(
                        f"Shift {conflict.name} is already open at this station.")

    def write(self, vals):
        if "status" in vals:
            for rec in self:
                old = rec.status
                new = vals["status"]
                if old != new:
                    if new not in ALLOWED_TRANSITIONS.get(old, set()):
                        raise ValidationError(
                            f"Cannot move shift from '{old}' to '{new}'. "
                            f"Allowed: {ALLOWED_TRANSITIONS.get(old) or 'none — terminal state'}.")
                    if new == "readings_captured":
                        rec._assert_all_opening_readings_present()
                    if new == "closing":
                        rec._assert_closing_readings_present()
                    if new == "closed" and not rec.journal_entry_id:
                        raise ValidationError(
                            "Journal Entry must be posted before shift can be Closed.")
        return super().write(vals)
```

This mirrors the ERPNext `before_save` hook exactly, using Odoo's `write()` override and `@api.constrains` instead of `doc_events`.

### 7.4 `fms.meter.reading` (Three Types, One Model)

The `meter_type` field is the differentiator — not separate models.

**Immutability:** Once a reading's `state` is `confirmed` (Odoo equivalent of ERPNext's `docstatus = 1`), `totalizer_value` cannot be changed. To correct: create a reading with `reading_position = amendment`. The original remains as evidence.

```python
class FmsMeterReading(models.Model):
    _name = "fms.meter.reading"
    _description = "Forecourt Meter Reading"

    name = fields.Char(default="New")
    shift_id = fields.Many2one("fms.shift", required=True, ondelete="cascade")
    pump_id = fields.Many2one("fms.pump", required=True)
    nozzle_number = fields.Integer(required=True)
    meter_type = fields.Selection([
        ("electronic_volume", "Electronic Volume"),
        ("electronic_cash", "Electronic Cash"),
        ("manual_mechanical", "Manual Mechanical"),
    ], required=True)
    reading_position = fields.Selection([
        ("shift_open", "Shift Open"), ("shift_close", "Shift Close"),
        ("spot_check", "Spot Check"), ("amendment", "Amendment"),
    ], required=True)
    observed_at = fields.Datetime(default=fields.Datetime.now)
    totalizer_value = fields.Float(digits=(16, 3))
    unit = fields.Selection([("litres", "Litres"), ("kes", "KES")], compute="_compute_unit", store=True)
    read_by_id = fields.Many2one("hr.employee", string="Read By")
    witnessed_by_id = fields.Many2one("hr.employee", string="Witnessed By")
    notes = fields.Text()
    superseded_by_id = fields.Many2one("fms.meter.reading")
    amendment_reason = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed")], default="draft")

    @api.depends("meter_type")
    def _compute_unit(self):
        for rec in self:
            rec.unit = "kes" if rec.meter_type == "electronic_cash" else "litres"

    @api.constrains("totalizer_value")
    def _check_positive(self):
        for rec in self:
            if rec.totalizer_value <= 0:
                raise ValidationError("Totalizer value must be greater than zero.")

    @api.constrains("totalizer_value", "reading_position")
    def _check_closing_not_below_opening(self):
        for rec in self:
            if rec.reading_position == "shift_close":
                opening = self.search([
                    ("shift_id", "=", rec.shift_id.id), ("pump_id", "=", rec.pump_id.id),
                    ("nozzle_number", "=", rec.nozzle_number),
                    ("meter_type", "=", rec.meter_type),
                    ("reading_position", "=", "shift_open"), ("state", "=", "confirmed"),
                ], limit=1)
                if not opening:
                    raise ValidationError(
                        f"No Shift Open reading for {rec.pump_id.display_name} / "
                        f"N{rec.nozzle_number} / {rec.meter_type}.")
                if rec.totalizer_value < opening.totalizer_value:
                    raise ValidationError(
                        f"Closing ({rec.totalizer_value}) < opening "
                        f"({opening.totalizer_value}). Meters only count forward.")

    def write(self, vals):
        if "totalizer_value" in vals:
            for rec in self:
                if rec.state == "confirmed" and rec.totalizer_value != vals["totalizer_value"]:
                    raise ValidationError(
                        f"Confirmed Meter Reading {rec.name} is immutable. "
                        f"Create an Amendment instead.")
        if vals.get("reading_position") == "amendment" or any(
                r.reading_position == "amendment" for r in self):
            if not (vals.get("amendment_reason") or all(r.amendment_reason for r in self)):
                raise ValidationError("Amendment readings require an Amendment Reason.")
        return super().write(vals)

    def action_confirm(self):
        self.write({"state": "confirmed"})
```

### 7.5 `fms.meter.validation.result`

Computed output of Check A and Check B per nozzle. Auto-generated; never manually edited (Odoo: all fields `readonly=True`, created only from server code, no create/write rights granted to regular users via `ir.model.access.csv`).

```python
CHECK_A_PASS_KES   = 5.0
CHECK_A_WARN_KES   = 20.0
CHECK_B_PASS_PCT   = 0.30
CHECK_B_WARN_PCT   = 0.50
CHECK_B_TAMPER_PCT = 1.00

class FmsMeterValidationResult(models.Model):
    _name = "fms.meter.validation.result"
    _description = "Meter Validation Result"

    shift_id = fields.Many2one("fms.shift", required=True, ondelete="cascade")
    pump_id = fields.Many2one("fms.pump", required=True)
    nozzle_number = fields.Integer()
    fuel_product_id = fields.Many2one("product.product")
    shift_rate = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="shift_id.currency_id")
    elec_vol_sold = fields.Float()
    elec_cash_sold = fields.Monetary(currency_field="currency_id")
    mech_vol_sold = fields.Float()
    expected_cash = fields.Monetary(currency_field="currency_id")
    check_a_discrepancy = fields.Monetary(currency_field="currency_id")
    check_a_status = fields.Selection([("pass", "Pass"), ("warning", "Warning"), ("fail", "Fail")])
    check_b_divergence_pct = fields.Float(digits=(8, 4))
    check_b_status = fields.Selection([
        ("pass", "Pass"), ("warning", "Warning"), ("fail", "Fail"), ("critical", "Critical")])
    overall_status = fields.Selection([
        ("pass", "Pass"), ("warning", "Warning"), ("fail", "Fail"), ("critical", "Critical")])
```

**Meter validation Python engine (`models/fms_meter_validation_result.py`, model method, run from the close-shift wizard):**

```python
SEVERITY = {"pass": 0, "warning": 1, "fail": 2, "critical": 3}

def _validate_nozzle(self, nd, shift):
    rate = self._get_rate(shift, nd["fuel_product_id"])
    elec_vol  = nd["elec_vol_sold"]
    elec_cash = nd["elec_cash_sold"]
    mech_vol  = nd["mech_vol_sold"]

    expected_cash = elec_vol * rate
    check_a_disc  = abs(elec_cash - expected_cash)
    check_b_pct   = abs(elec_vol - mech_vol) / elec_vol * 100 if elec_vol else 0.0

    check_a = "pass" if check_a_disc <= CHECK_A_PASS_KES else (
              "warning" if check_a_disc <= CHECK_A_WARN_KES else "fail")
    check_b = "pass" if check_b_pct <= CHECK_B_PASS_PCT else (
              "warning" if check_b_pct <= CHECK_B_WARN_PCT else (
              "critical" if check_b_pct > CHECK_B_TAMPER_PCT else "fail"))

    overall = max([check_a, check_b], key=lambda s: SEVERITY[s])

    if check_b == "critical":
        self._lock_pump(nd["pump_id"])

    return {
        "pump_id": nd["pump_id"], "nozzle_number": nd["nozzle_number"],
        "shift_rate": rate, "elec_vol_sold": elec_vol,
        "elec_cash_sold": elec_cash, "mech_vol_sold": mech_vol,
        "expected_cash": expected_cash,
        "check_a_discrepancy": check_a_disc, "check_a_status": check_a,
        "check_b_divergence_pct": round(check_b_pct, 4), "check_b_status": check_b,
        "overall_status": overall,
    }

def _lock_pump(self, pump_id):
    pump = self.env["fms.pump"].browse(pump_id)
    pump.is_active = False
    self.env["bus.bus"]._sendone(
        f"fms_pump_{pump_id}", "pump_locked",
        {"pump_id": pump_id, "reason": "Meter Check B Critical — possible tampering"})
    self.env["mail.message"].create({
        "model": "fms.pump", "res_id": pump_id,
        "body": "AUTO-LOCKED: Check B > 1% tamper threshold.",
    })
```

> Odoo's `bus.bus._sendone()` is the equivalent of Frappe's `frappe.publish_realtime()` — it pushes to any browser tabs subscribed to that bus channel.

### 7.6 `fms.tank.dip.reading`

Single model for all scenarios. `reading_type` and `reading_source` differentiate them.

```python
class FmsTankDipReading(models.Model):
    _name = "fms.tank.dip.reading"
    _description = "Tank Dip Reading"

    shift_id = fields.Many2one("fms.shift", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="shift_id.company_id", store=True)
    tank_location_id = fields.Many2one("stock.location", required=True,
                                        domain=[("fms_is_fuel_tank", "=", True)])
    reading_datetime = fields.Datetime(default=fields.Datetime.now)
    reading_type = fields.Selection([
        ("shift_open", "Shift Open"), ("shift_close", "Shift Close"),
        ("delivery_before", "Delivery Before"), ("delivery_after", "Delivery After"),
        ("spot", "Spot")], required=True)
    reading_source = fields.Selection([
        ("manual_dipstick", "Manual Dipstick"), ("atg_electronic", "ATG Electronic")])
    dip_height_mm = fields.Float()
    volume_observed_l = fields.Float()
    water_level_mm = fields.Float()
    calibration_chart_id = fields.Many2one("fms.tank.calibration.chart")
    read_by_id = fields.Many2one("hr.employee")

    @api.constrains("volume_observed_l", "tank_location_id")
    def _check_capacity(self):
        for rec in self:
            cap = rec.tank_location_id.fms_capacity_litres
            if cap and rec.volume_observed_l > cap:
                raise ValidationError("Observed volume exceeds tank capacity.")

    @api.constrains("water_level_mm")
    def _check_water(self):
        for rec in self:
            if rec.water_level_mm and rec.water_level_mm > 20:
                rec.message_post(body=f"⚠️ Water level {rec.water_level_mm}mm exceeds 20mm alert threshold.")
```

### 7.7 `fms.tank.calibration.chart`

Converts dip height (mm) to volume (litres) via EPRA-certified strapping table. Modelled as a header model with a `one2many` of chart rows (`fms.tank.calibration.chart.line`), equivalent to ERPNext's `chart_readings` child table.

```python
def derive_volume_from_dip(self, dip_height_mm, chart):
    rows = chart.line_ids.sorted("dip_height_mm")
    if dip_height_mm < rows[0].dip_height_mm or dip_height_mm > rows[-1].dip_height_mm:
        raise ValidationError(f"Dip {dip_height_mm}mm is outside calibration chart range.")
    for lo, hi in zip(rows, rows[1:]):
        if lo.dip_height_mm <= dip_height_mm <= hi.dip_height_mm:
            ratio = (dip_height_mm - lo.dip_height_mm) / (hi.dip_height_mm - lo.dip_height_mm)
            return lo.volume_ltrs + ratio * (hi.volume_ltrs - lo.volume_ltrs)
```

### 7.8 `fms.cashier.session`

One session per cashier per shift. Multiple sessions per shift are normal at Shell Maanzoni (4–5 per shift). Each cashier reconciles independently — matching the paper Cash Reconciliation Sheet.

```python
class FmsCashierSession(models.Model):
    _name = "fms.cashier.session"
    _description = "Cashier Session"

    shift_id = fields.Many2one("fms.shift", required=True, ondelete="cascade")
    cashier_id = fields.Many2one("hr.employee", required=True)
    till_id = fields.Char(string="Till ID")
    is_primary = fields.Boolean()
    float_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="shift_id.currency_id")
    actual_cash_close = fields.Monetary(currency_field="currency_id")
    counted_by_id = fields.Many2one("hr.employee", string="Counted By")
    verified_by_id = fields.Many2one("hr.employee", string="Verified By")
    pos_session_id = fields.Many2one("pos.session", string="Linked POS Session")
```

`pos_session_id` links each `fms.cashier.session` to the native Odoo `pos.session` the cashier opened on the till — Odoo's POS app already tracks opening/closing cash, sales, and payments per session, so FMS reuses that data rather than duplicating it (see §24.2).

### 7.9 `fms.cash.event`

Every cash movement: float, pickup, payout, safe drop.

```python
class FmsCashEvent(models.Model):
    _name = "fms.cash.event"
    _description = "Cash Event"

    shift_id = fields.Many2one("fms.shift", required=True, ondelete="cascade")
    cashier_session_id = fields.Many2one("fms.cashier.session", required=True)
    event_type = fields.Selection([
        ("float_issued", "Float Issued"), ("cash_pickup", "Cash Pickup"),
        ("payout", "Payout"), ("safe_drop", "Safe Drop")], required=True)
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="shift_id.currency_id")
    authorised_by_id = fields.Many2one("hr.employee", required=True)
    occurred_at = fields.Datetime(default=fields.Datetime.now)
    reference = fields.Char(help="Envelope number — required for Pickup/Safe Drop")

    @api.constrains("authorised_by_id", "cashier_session_id")
    def _check_dual_control(self):
        for rec in self:
            if rec.authorised_by_id == rec.cashier_session_id.cashier_id:
                raise ValidationError("Authoriser must differ from the session cashier.")

    @api.constrains("event_type", "reference")
    def _check_reference_required(self):
        for rec in self:
            if rec.event_type in ("cash_pickup", "safe_drop") and not rec.reference:
                raise ValidationError("Envelope/reference number is required for Pickup and Safe Drop.")
```

### 7.10 `fms.shift.reconciliation`

Computed summary. Fix source data, then recompute (a button, `action_compute_reconciliation`, re-runs the whole calculation idempotently — same pattern as the ERPNext "Compute Reconciliation" button).

**Child model 1 — `fms.shift.reconciliation.cashier.line`** (replicates paper Cash Reconciliation Sheet exactly):

| Field | Type | Notes |
|---|---|---|
| `cashier_id` | Many2one hr.employee | |
| `cashier_session_id` | Many2one fms.cashier.session | |
| `sales` | Monetary | Total sales billed to this cashier |
| `invoices` | Monetary | Credit invoices — non-cash, deducted |
| `pos_payments` | Monetary | POS/mobile money — non-cash, deducted |
| `visa_card` | Monetary | VISA/card — non-cash, deducted |
| `total_credits` | Monetary | `invoices + pos_payments + visa_card` |
| `receipts` | Monetary | Adjustments in (negative = out) |
| `payments_out` | Monetary | Cash pickups and safe drops |
| `expected_cash` | Monetary | `sales − total_credits + receipts − payments_out` |
| `actual_cash` | Monetary | Physically counted |
| `cash_over_under` | Monetary | `actual − expected` |

**Cash formula — verified against 17-05-2026 paper sheet (unchanged from ERPNext version):**
```
Swedi Abuti:   219,118.70 − 200,868.00 + (−1,000.00) − 2,950.00 = 14,300.70 ✓
Peter Mbeve:   149,724.50 − 136,131.00 + 0 − 410.00 = 13,183.50 ✓
Joseph Matale: 252,498.23 − 250,849.00 + 0 − 0 = 1,649.23 ✓
```

**Child model 2 — `fms.shift.reconciliation.tank.line`:**

| Field | Type | Notes |
|---|---|---|
| `tank_location_id` | Many2one stock.location | |
| `fuel_product_id` | Many2one product.product | |
| `opening_stock_l` | Float | From Shift Open dip |
| `deliveries_l` | Float | From accepted Fuel Delivery Dips |
| `elec_vol_sales_l` | Float | Σ Elec Vol for all nozzles on this tank |
| `mech_vol_sales_l` | Float | Σ Man Mech (cross-check) |
| `theoretical_closing_l` | Float | Opening + Deliveries − Sales |
| `actual_closing_l` | Float | From Shift Close dip |
| `variance_l` | Float | Theoretical − Actual |
| `variance_pct` | Float | |
| `classification` | Selection | Normal / Elevated / Critical / Gain |
| `variance_kes` | Monetary | `variance_l × average_cost` |

**Child model 3 — `fms.shift.reconciliation.nozzle.line`:**

| Field | Type | Notes |
|---|---|---|
| `pump_id` | Many2one fms.pump | |
| `nozzle_number` | Integer | |
| `elec_vol_sold` | Float | |
| `elec_cash_sold` | Monetary | |
| `mech_vol_sold` | Float | |
| `check_a_status` | Selection | Pass / Warning / Fail |
| `check_b_status` | Selection | Pass / Warning / Fail / Critical |

### 7.11 Other Key Models

**`fms.fuel.delivery.dip`** — links a `purchase.order` / incoming `stock.picking` to before/after dip readings; tracks truck reg, docket number, dip-measured vs docket variance; `state` field: `draft` / `accepted` / `disputed`.

**`fms.drive.off.record`** — fuel dispensed but not paid; auto-computes KES from volume × shift rate; requires manager authorisation; police reference required if ≥ KES 500; on confirm, posts a journal entry `DR Drive-Off Losses / CR Fuel Sales` via `account.move`.

**`fms.forecourt.transaction`** — PTS staging record; every PTS pump sale lands here before becoming a POS order (`pos.order`) at shift close; `pts_transaction_number` is the deduplication key (Odoo `_sql_constraints` unique index on `(pts_transaction_number, device_id)`).

**Pricing** — superseded by Odoo's native `product.pricelist` (see §24.1); a thin `fms.fuel.price.change.log` model retains an audit trail of EPRA gazette references and `approved_by` for prices above the EPRA cap.

**`fms.pts2.device`** — maps hardware `device_id` to an Odoo `company_id`; `last_seen` updated on every push.

**`fms.pump.configuration`** — maps `pts_pump_id` hardware to an `fms.pump` record with JSON fuel grade and tank mappings.

**`fms.fleet.card`** — card number, `res.partner` customer, grade restriction, credit limit, volume/amount limit per fill, RFID tag ID for PTS-2 authorisation.

---

## 8. Extending Native Odoo Models

All defined as `_inherit` model extensions inside the `fms` addon, applied automatically on module install/upgrade — the equivalent of ERPNext's `fms/fixtures/custom_field.json` loaded via `bench migrate`.

### 8.1 `pos.order` — FMS Forecourt Fields

```python
class PosOrder(models.Model):
    _inherit = "pos.order"

    fms_shift_id = fields.Many2one("fms.shift", string="Forecourt Shift")
    fms_pump_id = fields.Many2one("fms.pump")
    fms_pump_attendant_id = fields.Many2one("hr.employee", string="Pump Attendant")
    fms_etims_invoice_number = fields.Char(string="KRA eTIMS Confirmation")

    @api.model
    def create(self, vals):
        order = super().create(vals)
        if not order.fms_shift_id:
            open_shift = self.env["fms.shift"].search(
                [("company_id", "=", order.company_id.id), ("status", "=", "open")],
                limit=1, order="opened_at desc")
            order.fms_shift_id = open_shift
        return order

    def action_pos_order_paid(self):
        for order in self:
            if not order.fms_pump_attendant_id:
                raise ValidationError("Pump Attendant is required — blank/N/A is not permitted.")
        return super().action_pos_order_paid()
```

### 8.2 `account.move` (Sales Invoice equivalent) — FMS Forecourt Fields

Same pattern as POS, plus `fms_fleet_card_id`, `fms_vehicle_number`, `fms_etims_invoice_number`. Applied via `_inherit = "account.move"` with `invoice_filter_type_domain = 'sale'` view inheritance.

### 8.3 `stock.picking` (Purchase Receipt / GRN equivalent) — FMS Fuel Delivery Fields

```python
class StockPicking(models.Model):
    _inherit = "stock.picking"

    fms_delivery_dip_id = fields.Many2one("fms.fuel.delivery.dip")
    fms_transporter_id = fields.Many2one("res.partner", string="Transporter")
    fms_vehicle_reg = fields.Char(string="Truck Registration")
    fms_docket_number = fields.Char()
    fms_driver_name = fields.Char()
    fms_expected_qty_l = fields.Float()
    fms_dip_before_l = fields.Float()
    fms_dip_after_l = fields.Float()
    fms_sales_during_offload_l = fields.Float()
    fms_received_qty_l = fields.Float(compute="_compute_received_qty", store=True)
    fms_delivery_variance_l = fields.Float(compute="_compute_received_qty", store=True)
    fms_shift_id = fields.Many2one("fms.shift")
    fms_variance_approved_by_id = fields.Many2one("hr.employee")

    @api.depends("fms_dip_before_l", "fms_dip_after_l", "fms_sales_during_offload_l", "fms_expected_qty_l")
    def _compute_received_qty(self):
        for rec in self:
            rec.fms_received_qty_l = (rec.fms_dip_after_l - rec.fms_dip_before_l) + rec.fms_sales_during_offload_l
            rec.fms_delivery_variance_l = rec.fms_expected_qty_l - rec.fms_received_qty_l
```

### 8.4 `stock.location` — FMS Tank Fields

`fms_is_fuel_tank` (Boolean), `fms_capacity_litres` (Float), `fms_pts2_tank_number` (Integer), `fms_fuel_product_id` (Many2one product.product) — already shown in §6.4.

---

## 9. Manual Station Workflows

### 9.1 Tank Calibration Chart Setup (One-Time Per Tank)

1. Obtain strapping table from EPRA-certified surveyor
2. `Inventory → Configuration → FMS Tank Calibration Charts → New`; enter tank, capacity, calibration date, certifier, certificate number
3. Enter every row from the strapping table in the `Calibration Lines` tab (one2many editable list, same UX as ERPNext's child table grid)
4. Save — volume auto-derives from dip height thereafter via the computed field button. Recalibrate annually.

### 9.2 Manual Dip Reading

1. Take 3 tape readings, average
2. `FMS → Operations → Tank Dip Readings → New` (works fine on Odoo's responsive mobile web client)
3. Select Tank, Reading Type, `reading_source = Manual Dipstick`
4. Enter `dip_height_mm` and `water_level_mm`
5. `volume_observed_l` auto-calculated via calibration chart on save (`@api.onchange` or stored `compute`)

### 9.3 Meter Reading Entry Procedure

*Print and laminate for each pump island — content unchanged from the legacy procedure:*

```
┌──────────────────────────────────────────────────────────┐
│  SHIFT OPEN / CLOSE — METER READING PROCEDURE            │
│                                                          │
│  For EACH active nozzle, record THREE readings:          │
│                                                          │
│  1. Electronic Volume (L)                                │
│     Read LITRES from the digital display                 │
│     Write ALL digits including decimals                  │
│     Example: 171,275,183.070                             │
│                                                          │
│  2. Electronic Cash (KES)                                │
│     Read KES from the digital display                    │
│     The number will be in the millions — write it all    │
│     Example: 29,387,277.20                               │
│                                                          │
│  3. Manual Mechanical (L)                                │
│     Read the number wheels in the panel window           │
│     Use a torch if needed — NEVER estimate               │
│     Example: 171,275,182.0                               │
│                                                          │
│  Before submitting: Elec Cash ÷ Elec Vol ≈ EPRA price   │
│  Man Mech should be close to Elec Vol                    │
│  Any mismatch → call your supervisor BEFORE closing      │
└──────────────────────────────────────────────────────────┘
```

---

## 10. PTS Controller Integration

### 10.1 Account Name Helper (centralised account resolution)

```python
# fms/models/fms_account_helper.py
from odoo import models

_DEFAULT_FIELD_MAP = {
    "till_active":         "till_active_account_id",
    "safe_main":           "safe_main_account_id",
    "mpesa_clearing":      "mpesa_clearing_account_id",
    "card_clearing":       "card_clearing_account_id",
    "cash_short_over":     "cash_short_over_account_id",
    "drive_off_losses":    "drive_off_losses_account_id",
}

class FmsAccountHelper(models.AbstractModel):
    _name = "fms.account.helper"
    _description = "FMS Account Resolution Helper"

    def get_account(self, short_name, company):
        prefs = self.env["fms.site.preferences"].search(
            [("company_id", "=", company.id)], limit=1)
        field_name = _DEFAULT_FIELD_MAP.get(short_name)
        account = prefs[field_name] if (prefs and field_name) else False
        if not account:
            raise UserError(f"No account mapping for '{short_name}' on {company.name}.")
        return account

    def get_fuel_accounts(self, product, company):
        # Odoo resolves sales/COGS/inventory accounts natively via the
        # product's product.category (Income Account, Expense Account,
        # Stock Valuation Account) — no manual mapping table needed.
        categ = product.categ_id
        return {
            "sales": product.property_account_income_id or categ.property_account_income_categ_id,
            "cogs": product.property_account_expense_id or categ.property_account_expense_categ_id,
            "inventory": categ.property_stock_valuation_account_id,
            "wetstock_variance": categ.fms_wetstock_variance_account_id,  # custom field added on product.category
        }
```

> **Simplification vs ERPNext:** Odoo already resolves Sales/COGS/Inventory accounts per product via `product.category` (`property_account_income_categ_id`, `property_account_expense_categ_id`, `property_stock_valuation_account_id`). FMS only needs to add **one** extra field on `product.category` for the wetstock-variance account — there is no need to reinvent ERPNext's full `get_account()` short-name dictionary for the fuel sales/COGS/inventory triad.

### 10.2 PTS-2 HTTP Receiver (Odoo Controller)

Odoo exposes HTTP endpoints via `http.Controller` classes with `@http.route`. Because the endpoint must accept unauthenticated traffic from the PTS-2 device (it authenticates itself via HMAC, not an Odoo session), use `auth="public"` and `csrf=False`, then verify the signature manually — the direct equivalent of ERPNext's `@frappe.whitelist(allow_guest=True)`.

```python
# fms/controllers/pts2.py
import hmac, hashlib, json
from odoo import http
from odoo.http import request

class Pts2Controller(http.Controller):

    @http.route("/fms/pts2/receive", type="http", auth="public",
                methods=["POST"], csrf=False)
    def receive(self, **kwargs):
        body = request.httprequest.get_data()
        sig = request.httprequest.headers.get("X-Signature", "")

        device_id_hint = json.loads(body).get("DeviceId")
        device = request.env["fms.pts2.device"].sudo().search(
            [("device_id", "=", device_id_hint), ("active", "=", True)], limit=1)
        if not device:
            return request.make_json_response({"error": "Unknown device"}, status=404)

        secret = device.company_id.fms_pts2_secret_key
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return request.make_json_response({"error": "Invalid signature"}, status=401)

        data = json.loads(body)
        device.sudo().write({"last_seen": fields_datetime_now()})

        handlers = {
            "PumpTransaction": self._handle_pump_transaction,
            "TankMeasurement": self._handle_tank_measurement,
            "Alert": self._handle_alert,
        }
        handler = handlers.get(data.get("RecordType"))
        if handler:
            handler(data, device.company_id)
        return request.make_json_response({"status": "ok"})

    def _handle_pump_transaction(self, data, company):
        tx_number = data.get("TransactionNumber")
        env = request.env
        # Deduplication — silently skip PTS retries
        existing = env["fms.forecourt.transaction"].sudo().search([
            ("pts_transaction_number", "=", tx_number), ("company_id", "=", company.id)
        ], limit=1)
        if existing:
            return

        config = env["fms.pump.configuration"].sudo().search([
            ("pts_pump_id", "=", str(data.get("PumpNumber"))),
            ("company_id", "=", company.id), ("is_active", "=", True),
        ], limit=1)
        if not config:
            env["ir.logging"].sudo().create({
                "name": "fms.pts2", "type": "server", "level": "ERROR",
                "message": f"No pump config for pump {data.get('PumpNumber')}, {company.name}",
                "path": "fms.controllers.pts2", "line": "0", "func": "_handle_pump_transaction",
            })
            return

        fuel_grade = (config.fuel_grade_mapping or {}).get(str(data.get("FuelGradeId")))
        shift = env["fms.shift"].sudo().search(
            [("company_id", "=", company.id), ("status", "=", "open")],
            order="opened_at desc", limit=1)

        env["fms.forecourt.transaction"].sudo().create({
            "company_id": company.id, "shift_id": shift.id if shift else False,
            "pump_id": config.pump_id.id, "fuel_grade": fuel_grade,
            "posting_datetime": data.get("SaleEnd"),
            "quantity_litres": data.get("Volume"),
            "unit_price": data.get("Price"),
            "total_amount": (data.get("Volume") or 0) * (data.get("Price") or 0),
            "pts_transaction_number": tx_number,
            "payment_mode": "cash", "state": "draft",
        })
```

> **Note on `csrf=False` + `auth="public"`:** This is the standard Odoo pattern for webhook-style endpoints (used the same way for payment-provider webhooks, e.g. Stripe/Mpesa callbacks in core Odoo addons). HMAC verification replaces Odoo's session/CSRF protection for this specific endpoint, exactly mirroring ERPNext's `allow_guest=True` + manual HMAC check.

### 10.3 PTS-2 Station Configuration

| Setting | Value |
|---|---|
| Domain Name | `fms.shelldomain.co.ke` |
| URI | `/fms/pts2/receive` |
| Port | 443 (HTTPS) |
| Secret Key | Stored on `res.company.fms_pts2_secret_key` (custom field) |
| SD Card Logging | ✅ **Required for upload retry** |
| WebSocket URI | `/fms/pts2/ws` (see §10.5) |

### 10.4 Background Jobs (`ir.cron` — equivalent of `hooks.py` `scheduler_events`)

```xml
<!-- fms/data/ir_cron_data.xml -->
<odoo>
    <record id="ir_cron_watchdog_pts_devices" model="ir.cron">
        <field name="name">FMS: Watchdog check PTS devices</field>
        <field name="model_id" ref="model_fms_pts2_device"/>
        <field name="state">code</field>
        <field name="code">model.watchdog_check_pts_devices()</field>
        <field name="interval_number">5</field>
        <field name="interval_type">minutes</field>
    </record>

    <record id="ir_cron_daily_shift_summary" model="ir.cron">
        <field name="name">FMS: Send daily shift summary</field>
        <field name="model_id" ref="model_fms_shift"/>
        <field name="state">code</field>
        <field name="code">model.send_daily_shift_summary()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
    </record>

    <record id="ir_cron_check_calibration_due" model="ir.cron">
        <field name="name">FMS: Check calibration due dates</field>
        <field name="model_id" ref="model_fms_tank_calibration_chart"/>
        <field name="state">code</field>
        <field name="code">model.check_calibration_due_dates()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
    </record>

    <record id="ir_cron_check_stale_open_shifts" model="ir.cron">
        <field name="name">FMS: Check stale open shifts</field>
        <field name="model_id" ref="model_fms_shift"/>
        <field name="state">code</field>
        <field name="code">model.check_stale_open_shifts()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">hours</field>
    </record>
</odoo>
```

This is the direct equivalent of ERPNext's `scheduler_events = {"all": [...], "daily": [...], "hourly": [...]}` dictionary in `hooks.py` — except each `ir.cron` record is its own scheduled job rather than a grouped dictionary, which is normal Odoo practice and gives finer per-job control (enable/disable, change frequency, view run history) directly from the UI under **Settings → Technical → Scheduled Actions**.

### 10.5 WebSocket / Real-Time Commands (price push, pump auth, RFID sync)

Odoo does not natively terminate arbitrary external WebSocket clients the way Frappe does — Odoo's own `bus.bus` websocket is for pushing events to **Odoo's own browser sessions**, not for accepting connections from third-party hardware like the PTS-2.

Two supported patterns, in order of recommendation:

**Pattern A — Odoo-initiated HTTP commands (recommended, simplest).**
Skip an inbound WebSocket entirely. The PTS-2's Web Server API (see companion PTS-2 guide §6) accepts synchronous HTTP commands. Odoo calls these directly with `requests` whenever a command is needed (price push, pump authorise, RFID sync) — no persistent connection to maintain on the Odoo side.

```python
# fms/models/fms_pts2_commands.py
import requests
from odoo import models

class FmsPts2Commands(models.AbstractModel):
    _name = "fms.pts2.commands"
    _description = "PTS-2 Outbound Commands (HTTP Web Server API)"

    def push_price_update(self, device, grades):
        # grades: [{"id": 1, "price": "214.200"}, ...]
        url = f"https://{device.ip_address}/config/grades"
        requests.post(url, json={"grades": grades},
                      auth=(device.api_user, device.api_password), timeout=5, verify=True)

    def authorize_pump(self, device, pump_number, preset_type=0, preset_value=None):
        url = f"https://{device.ip_address}/pumps/{pump_number}"
        payload = {"action": "authorize", "preset_type": preset_type}
        if preset_value:
            payload["preset_value"] = preset_value
        requests.post(url, json=payload,
                      auth=(device.api_user, device.api_password), timeout=5)

    def sync_rfid_tags(self, device):
        employees = self.env["hr.employee"].search([
            ("company_id", "=", device.company_id.id), ("fms_rfid_tag_id", "!=", False),
        ])
        tags = [{
            "Id": e.fms_rfid_tag_id, "Name": e.name,
            "Length": len(e.fms_rfid_tag_id), "Valid": e.active,
        } for e in employees]
        url = f"https://{device.ip_address}/config/tags"
        requests.post(url, json={"tags": tags},
                      auth=(device.api_user, device.api_password), timeout=10)
```

**Pattern B — PTS Bridge sidecar (only if sub-second pump status streaming is required).**
Run a small standalone Python service (FastAPI/`websockets`) that terminates the PTS-2's persistent WebSocket connection, then relays each status frame into Odoo via XML-RPC/JSON-RPC (`odoorpc`) and pushes UI updates through `bus.bus._sendone()`. This bridge is a separate deployable, not part of the `fms` Odoo addon, and is only needed for Phase 3 real-time pump-status dashboards (§19, Phase 3) — Phase 1–2 do not require it, since the HTTP push (§10.2) already delivers every completed transaction.

```python
# pts2_bridge/bridge.py  (standalone process, not inside Odoo)
import asyncio, websockets, json, odoorpc

odoo = odoorpc.ODOO("fms.shelldomain.co.ke", port=443, protocol="jsonrpc+ssl")
odoo.login("shell_maanzoni_db", "pts_bridge_user", "***")

async def handle_pts2(websocket):
    async for message in websocket:
        frame = json.loads(message)
        if frame.get("RecordType") == "Status":
            odoo.env["bus.bus"].sudo()._sendone(
                f"fms_pump_status_{frame['DeviceId']}", "pts2_status", frame)

async def main():
    async with websockets.serve(handle_pts2, "0.0.0.0", 8765):
        await asyncio.Future()

asyncio.run(main())
```

`→ companion PTS-2 guide §5 and §9` for the full WebSocket command catalogue this bridge (or Pattern A's HTTP calls) needs to support.

### 10.6 `__manifest__.py` (Complete, equivalent of ERPNext `hooks.py`)

```python
# fms/__manifest__.py
{
    "name": "Forecourt Management System (FMS)",
    "summary": "Shift-based fuel station operations, wetstock and cash reconciliation",
    "version": "17.0.1.0.0",
    "category": "Inventory/Fuel Retail",
    "depends": ["stock", "point_of_sale", "account", "hr", "purchase", "sale", "mail"],
    "data": [
        "security/fms_security_rules.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "data/ir_sequence_data.xml",
        "views/fms_shift_views.xml",
        "views/fms_meter_reading_views.xml",
        "views/fms_tank_dip_reading_views.xml",
        "views/fms_cashier_session_views.xml",
        "views/fms_cash_event_views.xml",
        "views/fms_fuel_delivery_dip_views.xml",
        "views/fms_shift_reconciliation_views.xml",
        "views/fms_drive_off_record_views.xml",
        "views/fms_site_preferences_views.xml",
        "views/fms_dashboard_views.xml",
        "views/fms_menus.xml",
        "report/fms_reports.xml",
        "wizards/fms_bulk_price_update_wizard_views.xml",
        "wizards/fms_close_shift_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "OPL-1",
}
```

Model-level `_inherit`/business-logic hooks (e.g. blocking `pos.order` confirmation without an attendant — §8.1, posting a journal entry on Drive-Off confirm) live as ordinary Python method overrides inside each model file rather than a centralized `doc_events` dictionary; Odoo's ORM convention is "override the method on the model that owns the behaviour" rather than Frappe's external hook registration table. This is functionally equivalent but spreads the same logic across `models/*.py` instead of one `hooks.py`.

---

## 11. Shift Lifecycle & Cash Reconciliation

### 11.1 Opening a Shift

1. Supervisor creates `fms.shift → New`: company, date, label, cashier, supervisor
2. Lock EPRA rates from the active `product.pricelist` (see §24.1): `rate_pms_unl = 214.20`, `rate_pms_vp = 229.00`, `rate_ago = 242.90`
3. Create an `fms.cashier.session` for each cashier (and open the matching `pos.session` in Odoo's POS app); issue floats → `fms.cash.event: float_issued`
4. Opening dips for every active tank → `fms.tank.dip.reading: shift_open`
5. Opening meter readings for every active nozzle — **all three types each**:
   - Electronic Volume (L) — from digital display
   - Electronic Cash (KES) — from digital display
   - Manual Mechanical (L) — from number wheels
6. Once all opening readings are confirmed → transition to `readings_captured`
7. Status → `open` — sales can begin (Odoo's `pos.order` `create()` override in §8.1 auto-links to this shift)

### 11.2 During the Shift

- All POS sales: correct payment method and named pump attendant (never blank/N/A — enforced server-side in §8.1)
- Fleet/credit sales → Odoo `account.move` customer invoice (not POS) — these populate the `Invoices` column in reconciliation
- Cash pickup when till > KES 30,000: `fms.cash.event: cash_pickup` + supervisor sign + envelope number — populates `Pymts` column
- Fuel delivery: §12
- Drive-off: `fms.drive.off.record` with manager authorisation
- If second cashier takes over: new `fms.cashier.session` (and new `pos.session`), not a new Shift

### 11.3 Closing a Shift

1. Read all pump displays — enter **all three closing meter readings** per nozzle
2. Take closing dips for all active tanks
3. Each cashier physically counts till and enters `actual_cash_close` in their `fms.cashier.session` (or it auto-fills from the linked `pos.session.cash_register_balance_end_real`)
4. Enter non-cash totals per cashier: Invoices (credit sales), POS (mobile money), VISA (card) — these can be pre-filled from Odoo's POS payment-method breakdown and adjusted
5. Status → `closing`
6. Supervisor runs the **Close Shift wizard** → "Run Meter Validation" action → `fms.meter.validation.result` per nozzle
7. Resolve any Check B Fail/Critical (Amendment reading or pump inspection) and re-run
8. Supervisor clicks "Compute Reconciliation" in the same wizard → `fms.shift.reconciliation` record created
9. Review per-cashier summaries (matches the paper Cash Rec Sheet)
10. Review per-tank wetstock summaries
11. If all balanced → Approve → Post Journal Entry → Status → `closed`
12. If Critical variance → Status → `disputed` → investigate before posting

### 11.4 Automated Journal Entry (`account.move`)

```python
# fms/models/fms_shift_reconciliation.py (excerpt)
def post_shift_journal_entry(self):
    self.ensure_one()
    sr = self
    shift = sr.shift_id
    if sr.journal_entry_id:
        raise UserError("Journal Entry already posted. Reverse before re-posting.")
    if sr.requires_approval and not sr.approved_by_id:
        raise UserError("Manager approval required before posting the journal entry.")

    company = shift.company_id
    journal = self.env["account.journal"].search(
        [("company_id", "=", company.id), ("type", "=", "general")], limit=1)
    lines = []

    # Revenue credits — one per active product
    for ps in sr.product_summary_ids:
        accts = self.env["fms.account.helper"].get_fuel_accounts(ps.fuel_product_id, company)
        if ps.gross_revenue:
            lines.append((0, 0, {"account_id": accts["sales"].id, "credit": ps.gross_revenue}))

    # Tender debits + cash variance — per cashier
    helper = self.env["fms.account.helper"]
    for cs in sr.cashier_line_ids:
        if cs.actual_cash > 0:
            lines.append((0, 0, {
                "account_id": helper.get_account("till_active", company).id,
                "debit": cs.actual_cash}))
        if cs.visa_card > 0:
            lines.append((0, 0, {
                "account_id": helper.get_account("card_clearing", company).id,
                "debit": cs.visa_card}))
        if cs.pos_payments > 0:
            lines.append((0, 0, {
                "account_id": helper.get_account("mpesa_clearing", company).id,
                "debit": cs.pos_payments}))
        cv = cs.cash_over_under
        if abs(cv) > 0.01:
            acct = helper.get_account("cash_short_over", company)
            lines.append((0, 0, {
                "account_id": acct.id,
                "debit": abs(cv) if cv < 0 else 0,
                "credit": cv if cv > 0 else 0}))

    # Wetstock variance per tank
    for ts in sr.tank_line_ids:
        var_kes = ts.variance_kes
        if abs(var_kes) >= 1.0:
            accts = helper.get_fuel_accounts(ts.fuel_product_id, company)
            if var_kes > 0:
                lines.append((0, 0, {"account_id": accts["wetstock_variance"].id, "debit": var_kes}))
                lines.append((0, 0, {"account_id": accts["inventory"].id, "credit": var_kes}))
            else:
                lines.append((0, 0, {"account_id": accts["wetstock_variance"].id, "credit": abs(var_kes)}))
                lines.append((0, 0, {"account_id": accts["inventory"].id, "debit": abs(var_kes)}))

    total_dr = sum(l[2].get("debit", 0) for l in lines)
    total_cr = sum(l[2].get("credit", 0) for l in lines)
    if abs(total_dr - total_cr) > 0.05:
        raise UserError(f"Journal entry out of balance: DR {total_dr:.2f} / CR {total_cr:.2f}")

    move = self.env["account.move"].create({
        "move_type": "entry",
        "journal_id": journal.id,
        "date": shift.shift_date,
        "ref": f"Shift close — {shift.name} | {shift.cashier_id.name} | {shift.supervisor_id.name}",
        "line_ids": lines,
        "company_id": company.id,
    })
    move.action_post()

    sr.journal_entry_id = move.id
    shift.journal_entry_id = move.id
    return move
```

**Posted journal entry for a Shell Maanzoni-style shift (mixed cashiers, mixed tenders) — unchanged figures:**

```
# Revenue credits
CR  Fuel Sales — PMS Unleaded      204,785.65   (955.99 L × 214.20)
CR  Fuel Sales — AGO Diesel        414,526.49   (1,702.44 L × 242.90)

# Till debits per cashier (actual cash counted)
DR  Till — Active                   13,200.00   (Swedi Abuti actual)
DR  Till — Active                      250.00   (Joel Musembi actual)
DR  Till — Active                   13,300.00   (Peter Mbeve actual)
DR  Till — Active                    1,650.00   (Joseph Matale actual)

# Non-cash debits
DR  Card Payment Clearing           33,810.00   (VISA total)
DR  MPesa Clearing                  16,500.00   (POS total)
DR  Accounts Receivable            537,538.00   (Invoices total)

# Cash Short / Over per cashier
DR  Cash Short / Over                1,100.70   (Swedi — short)
CR  Cash Short / Over                  116.50   (Peter — over)
CR  Cash Short / Over                    0.77   (Joseph — over)
```

> Note: Odoo's POS module already posts its own journal entries for each `pos.session` closing (cash/card/Mpesa receivables against revenue, per Odoo's standard POS accounting flow). The FMS journal entry above intentionally posts **only the variance lines** — see §23 and §30.3 for the architectural reasoning carried over from the ERPNext version: revenue and COGS are posted in real time by the POS/Invoicing apps, and the shift-close entry exists purely to true-up wetstock and cash variances. The template above is shown in full (as in the original ERPNext guide) for clarity on what the *complete* picture of a shift's accounting looks like across both the POS-native entries and the FMS variance entry — see §30.3 for the corrected, variance-only posting scope.

---

## 12. Fuel Delivery (Receipt) Workflow

### 12.1 Delivery Variance Formula

```
received_qty = (dip_after − dip_before) + sales_during_offload
variance     = expected_qty − received_qty
```

Positive variance = supplier delivered less than docket. Negative = excess (rare, also investigate).

### 12.2 Workflow

1. Truck arrives → record truck reg, driver, docket number, fuel product, docket volume on a new `fms.fuel.delivery.dip`
2. `fms.tank.dip.reading → delivery_before`
3. Offloading begins; normal dispensing continues
4. Offloading ends → wait 10–15 minutes for fuel to settle
5. `fms.tank.dip.reading → delivery_after`
6. System computes `dip_measured = after − before` (stored compute field)
7. For PTS sites: `sales_during_offload` auto-calculated from `fms.forecourt.transaction` records in the window; for manual: read pump meters before/after offload
8. If `|variance| ≤ 0.5%`: Accept → confirm the linked `purchase.order` and validate the `stock.picking` at the dip-measured volume (override the picking's `qty_done` to the dip-measured value, not the docket value — see §8.3 and §21)
9. If `|variance| > 0.5%`: Dispute → call supplier with dip evidence → do not validate the picking until resolved

---

## 13. Wetstock Reconciliation

### 13.1 Complete Formula

```python
# fms/models/fms_shift_reconciliation.py (excerpt)
def compute_tank_wetstock(self, shift, tank_location):
    Dip = self.env["fms.tank.dip.reading"]
    opening = Dip.search([
        ("shift_id", "=", shift.id), ("tank_location_id", "=", tank_location.id),
        ("reading_type", "=", "shift_open"),
    ], limit=1).volume_observed_l

    deliveries = sum(self.env["fms.fuel.delivery.dip"].search([
        ("shift_id", "=", shift.id), ("tank_location_id", "=", tank_location.id),
        ("state", "=", "accepted"),
    ]).mapped("dip_measured_l"))

    MeterReading = self.env["fms.meter.reading"]
    nozzles = self.env["fms.pump.nozzle"].search([("tank_location_id", "=", tank_location.id)])
    elec_vol = mech_vol = 0.0
    for nozzle in nozzles:
        domain_base = [
            ("shift_id", "=", shift.id), ("pump_id", "=", nozzle.pump_id.id),
            ("nozzle_number", "=", nozzle.nozzle_number), ("state", "=", "confirmed"),
        ]
        ev_open = MeterReading.search(domain_base + [
            ("meter_type", "=", "electronic_volume"), ("reading_position", "=", "shift_open")], limit=1)
        ev_close = MeterReading.search(domain_base + [
            ("meter_type", "=", "electronic_volume"), ("reading_position", "=", "shift_close")], limit=1)
        mm_open = MeterReading.search(domain_base + [
            ("meter_type", "=", "manual_mechanical"), ("reading_position", "=", "shift_open")], limit=1)
        mm_close = MeterReading.search(domain_base + [
            ("meter_type", "=", "manual_mechanical"), ("reading_position", "=", "shift_close")], limit=1)
        if ev_open and ev_close:
            elec_vol += ev_close.totalizer_value - ev_open.totalizer_value
        if mm_open and mm_close:
            mech_vol += mm_close.totalizer_value - mm_open.totalizer_value

    theoretical = opening + deliveries - elec_vol
    actual = Dip.search([
        ("shift_id", "=", shift.id), ("tank_location_id", "=", tank_location.id),
        ("reading_type", "=", "shift_close"),
    ], limit=1).volume_observed_l

    variance_l = theoretical - actual
    denom = opening + deliveries
    variance_pct = (variance_l / denom * 100) if denom else 0.0
    abs_pct = abs(variance_pct)

    if variance_l < 0 and abs_pct > 0.50:    classification = "critical"
    elif variance_l < 0 and abs_pct > 0.30:  classification = "elevated"
    elif variance_l > 0 and abs_pct > 0.30:  classification = "gain"
    else:                                    classification = "normal"

    return {
        "opening_stock_l": opening, "deliveries_l": deliveries,
        "elec_vol_sales_l": elec_vol, "mech_vol_sales_l": mech_vol,
        "theoretical_closing_l": theoretical, "actual_closing_l": actual,
        "variance_l": variance_l, "variance_pct": round(variance_pct, 4),
        "classification": classification,
    }
```

This is a like-for-like port of the ERPNext `compute_tank_wetstock()` SQL/Python hybrid — implemented here using the Odoo ORM (`search`/`mapped`) instead of raw SQL joins, since Odoo's ORM is idiomatic for this kind of per-shift aggregation at typical station data volumes. For HQ-wide trend reports across thousands of shifts, the equivalent raw-SQL approach (`self.env.cr.execute(...)`) is used instead — see §27.2.3.

### 13.2 Variance Classification

| Metric | Normal (Auto-Approve) | Elevated (Review) | Critical (Block) |
|---|---|---|---|
| Wetstock loss % | ≤ 0.3% | 0.3–0.5% | > 0.5% |
| Wetstock gain % | — | Any > 0.3% | — (always flag) |
| Cash variance (KES) | ≤ 50 | 50–200 | > 200 |
| Check A discrepancy | ≤ KES 5 | KES 5–20 | > KES 20 |
| Check B divergence | ≤ 0.30% | 0.30–0.50% | > 0.50%; > 1.0% = lock pump |

### 13.3 Meter-Based Theft Detection

The legacy system shows `Var(Ltrs)` (Elec Vol − Man Mech). The Odoo FMS adds a further check: comparing the pump totalizer increment against billed `pos.order.line` + `account.move.line` volumes per nozzle. If a pump's totalizer shows 350 litres dispensed but only 320 litres appear in invoices for that nozzle, 30 litres were dispensed without being billed — fraud by a specific attendant.

---

## 14. Fleet Cards & Credit Customers

**`fms.fleet.card` model:** card number, `res.partner` customer, grade restriction, credit limit, volume/amount limit per fill, RFID tag for PTS-2 authorisation, expiry date.

**Authorisation flow (PTS-2):** Driver presents card → PTS-2 reads RFID → FMS checks active/limit/grade → `authorize_pump()` HTTP command sent to PTS-2 (§10.5, Pattern A) → pump unlocks → `fms.forecourt.transaction` with `payment_mode = fleet_card` → customer invoice (`account.move`) at shift close.

**Monthly cycle:** Customer invoices for credit customers at shift close → Odoo's native **Follow-up/Statements** feature generates the monthly statement → `account.payment` clears the receivable, exactly as in standard Odoo Accounting.

---

## 15. Kenya Compliance

**VAT (16%):** Use Odoo's Kenya fiscal localization (`l10n_ke`) tax `VAT 16%`, mapped to a `VAT Payable` account. Apply as the default customer tax on all fuel products and on the POS pricelist/fiscal position.

**Excise Duty:** Embedded in supplier invoice price. Model as **Additional Landed Costs** on the vendor bill — Odoo's native `stock.landed.cost` model, linked to the `stock.picking` for the delivery, with the excise component allocated by quantity. Odoo automatically adjusts the product's average cost upward, same effect as ERPNext's Landed Cost Voucher.

**eTIMS Integration:** On `pos.order` and `account.move` confirmation (`action_pos_order_paid` / `action_post` overrides), POST to the KRA eTIMS API. Store the returned invoice number and QR code on `fms_etims_invoice_number`. Log failures via `ir.logging` but do not block confirmation — flag for manual retry through a dedicated "eTIMS Pending" filter/kanban stage.

**EPRA Price Cap Validation:** On the Bulk Price Update wizard (§26.2) and on direct `product.pricelist.item` writes, if `new_price > epra_max_price` and no `approved_by` is set, raise a `ValidationError`. If approved, allow with a logged warning (`mail.message` on the pricelist item).

---

## 16. Security & Data Isolation

Odoo's **Multi-Company Rules** (built into `base`) filter most stock/sales/account list views, reports, and forms automatically once a user's `company_ids` is restricted. The **FMS `company_id` field** on every FMS model, combined with the explicit `ir.rule` shown in §6.6, extends the same protection to all custom FMS models.

> **Critical for SQL-based reports:** Odoo's record rules do **not** automatically filter raw `self.env.cr.execute()` SQL queries — exactly the same caveat as ERPNext's Query Reports. Every custom FMS SQL report (§27.2) must include an explicit `WHERE company_id = ANY(%(company_ids)s)` clause, and the calling Python method must pass `self.env.companies.ids`, not assume the ORM has already filtered.

**PTS-2 HMAC:** `hmac.compare_digest()` (constant-time) prevents timing attacks — identical implementation to the ERPNext version (§10.2 above).

### Role Permission Matrix

| Model | HQ Mgr | HQ Audit | Site Mgr | Supervisor | Cashier |
|---|---|---|---|---|---|
| `fms.shift` | RW | R | RW | RW | R |
| `fms.meter.reading` | RW+Amend | R | RW | RW | R |
| `fms.cash.event` | RW+Cancel | R | RW | RW | Create |
| `fms.shift.reconciliation` | RW | R | RW | R | — |
| `fms.drive.off.record` | RW | R | RW | RW | R |
| `fms.site.preferences` | RW | R | RW | R | — |

Implemented as standard Odoo `ir.model.access.csv` rows (one per `model × group` combination) plus the `ir.rule` company filter from §6.6. Where ERPNext distinguishes "Submit"/"Cancel" as separate document permissions, Odoo expresses the same idea through model `state` transitions guarded by `@api.constrains`/`write()` overrides plus ordinary `perm_write` — there is no separate "submit" ACL bit in Odoo, so the workflow guard itself (e.g. blocking edits once `state == 'confirmed'`, §7.4) carries that responsibility.

---

## 17. Offline Resilience & Error Handling

**PTS-2 offline:** Records queued on SD card; replayed on reconnect. Deduplication on `pts_transaction_number` (Odoo `_sql_constraints` unique key on `(pts_transaction_number, device_id)`) handles bulk replay. SD card logging must be enabled in PTS-2 Parameters (see companion guide).

**Generic PTS offline buffer:** Transactions written to a local buffer file when Odoo is unreachable; replayed via a small management command or `ir.cron` job that reads the buffer and calls the same controller logic as §10.2.

**Shift close without PTS:** Attendants read pump displays manually; enter closing totalizers via the standard `fms.meter.reading` form; proceed normally — no special-casing needed since manual entry uses the exact same model as PTS-fed data.

**Duplicate prevention:** `pts_transaction_number` + `device_id` unique constraint — duplicate inserts caught by Odoo's `psycopg2.IntegrityError`, caught in the controller and converted into a silent `{"status": "ok"}` response rather than a 500 error (mirrors the ERPNext behaviour exactly).

---

## 18. Server Infrastructure & DevOps

| Sites | RAM | CPU | Disk |
|---|---|---|---|
| 1–5 | 4 GB | 2 vCPU | 50 GB SSD |
| 5–20 | 8 GB | 4 vCPU | 100 GB SSD |
| 20–50 | 16 GB | 8 vCPU | 200 GB SSD |

(Sizing is unchanged from the ERPNext guide — Odoo's resource footprint per concurrent user is comparable to Frappe/ERPNext at this scale.)

**Nginx reverse proxy (Odoo's standard production config, with the FMS webhook path):**
```nginx
upstream odoo {
    server 127.0.0.1:8069;
}
upstream odoo-chat {
    server 127.0.0.1:8072;   # Odoo's longpolling / websocket worker
}

server {
    listen 443 ssl;
    server_name fms.shelldomain.co.ke;

    location /fms/pts2/receive {
        proxy_pass http://odoo;
        proxy_set_header Host $host;
        client_max_body_size 5m;
    }

    location /websocket {
        proxy_pass http://odoo-chat;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    location / {
        proxy_pass http://odoo;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

**SSL:** `sudo certbot --nginx -d fms.shelldomain.co.ke`

**Monitoring:** Odoo worker queue depth (`--workers` + `--limit-time-cpu`/`--limit-time-real` tuning, monitored via `odoo-bin`'s own logging or a process supervisor like systemd/supervisord); PTS-2 `last_seen` via the watchdog `ir.cron` job (alert if silent > 15 min, same as §10.4); disk usage alert at 80%; PostgreSQL slow query log (`log_min_duration_statement = 2000`).

---

## 19. Implementation Phases

### Phase 1 — Odoo Foundation (Weeks 1–2)

- [ ] Install Odoo 17/18; create Shell Kenya Limited + Shell Maanzoni sub-company (`res.company` with `parent_id`)
- [ ] Create Chart of Accounts with V-Power accounts separate from Unleaded (via `l10n_ke` + custom accounts)
- [ ] Create Products: `FUEL-PMS-UNL`, `FUEL-PMS-VP`, `FUEL-AGO` (storable, AVCO costing)
- [ ] Create tank `stock.location`s: Tank 1 (V-Power), Tank 2 (Unleaded), Tank 3 (Diesel)
- [ ] Create Security Groups; configure multi-company access per user
- [ ] Configure POS Configurations/Payment Methods, Kenya VAT 16%
- [ ] Create Employee records: Swedi Abuti, Peter Mbeve, Joseph Matale, Shadrack Kimulu, James Kitiapi, Joel Musembi, Abdirahman, etc.
- [ ] Create Vendor (`res.partner`) records for depots and transporters

### Phase 2 — FMS Addon & Manual Workflow (Weeks 3–4)

- [ ] Scaffold the `fms` addon (`odoo-bin scaffold fms addons/`); `pip install pyserial pymodbus websockets odoorpc`
- [ ] Build all FMS models including three-meter `fms.meter.reading` and `fms.meter.validation.result`
- [ ] Build `fms.drive.off.record`, `fms.site.preferences`, and all other models
- [ ] Define `_inherit` custom fields on `pos.order`, `account.move`, `stock.picking`, `stock.location`, `product.template`
- [ ] Configure `fms.site.preferences` for Maanzoni
- [ ] Create `fms.pump` and `fms.pump.nozzle` records matching actual hardware (UX/DX/VP pumps per island)
- [ ] Enter tank calibration charts for all three tanks
- [ ] Test full manual workflow: open shift → 3 meter readings per nozzle → dips → 5-cashier close → journal entry
- [ ] Verify per-cashier reconciliation matches paper sheet with 17-05-2026 data
- [ ] Configure eTIMS with KRA test environment

### Phase 3 — PTS Integration (Weeks 5–6)

- [ ] Order PTS-2 SDK from Technotrade; implement the `/fms/pts2/receive` controller against the SDK simulator
- [ ] Create `fms.pts2.device` registry; create `fms.pump.configuration` mappings for all pumps
- [ ] Decide Pattern A (HTTP commands) vs Pattern B (WebSocket bridge) per §10.5; deploy accordingly
- [ ] Test all data flows: pump transactions, tank measurements, alerts, price push, RFID sync
- [ ] Run 2-week parallel operation (paper + FMS) before cutting over

### Phase 4 — Multi-Site Rollout (Ongoing)

- [ ] Repeat Phases 1–3 for each additional site; HQ cross-site dashboard; train HQ Auditors
- [ ] Go-live site by site; 2-week parallel run per site

### Migration from Legacy System

1. Physical dip at cutover → an Odoo **Inventory Adjustment** (`stock.quant` count) for opening balances
2. Keep legacy read-only for 12 months; do not migrate history
3. Last shift on legacy, first shift on FMS — same calendar day
4. If FMS fails mid-shift: revert to paper dockets; reconcile retrospectively

---

## 20. Testing & Quality Assurance

Odoo tests use the standard `odoo.tests.common.TransactionCase` framework, run via `odoo-bin --test-enable -i fms --stop-after-init` (or `--test-tags fms` for selective runs). The same fixed test cases from the ERPNext suite are ported below, asserting identical numbers against identical inputs.

### 20.1 Unit Tests — Meter Validation

```python
# fms/tests/test_meter_validation.py
from odoo.tests.common import TransactionCase

class TestMeterValidation(TransactionCase):

    def _run(self, elec_vol=100.0, elec_cash=None, mech_vol=None,
             rate=214.20, product_code="FUEL-PMS-UNL"):
        if elec_cash is None: elec_cash = elec_vol * rate
        if mech_vol  is None: mech_vol  = elec_vol
        helper = self.env["fms.meter.validation.result"]
        nd = {"pump_id": 1, "nozzle_number": 2, "fuel_product_id": product_code,
              "elec_vol_sold": elec_vol, "elec_cash_sold": elec_cash, "mech_vol_sold": mech_vol}
        shift = type("S", (), {"rate_pms_unl": rate, "rate_pms_vp": 229.0, "rate_ago": 242.9})()
        return helper._validate_nozzle(nd, shift)

    def test_check_a_pass(self):
        r = self._run(elec_vol=100, elec_cash=100 * 214.20 + 3.0)
        self.assertEqual(r["check_a_status"], "pass")

    def test_check_a_warning(self):
        r = self._run(elec_vol=100, elec_cash=100 * 214.20 + 10.0)
        self.assertEqual(r["check_a_status"], "warning")

    def test_check_b_pass_typical_maanzoni(self):
        # U8 from live screen: 349.65 elec, 349.00 mech → 0.19% → Pass
        r = self._run(elec_vol=349.65, mech_vol=349.00)
        self.assertEqual(r["check_b_status"], "pass")

    def test_check_b_fail_u7(self):
        # U7 from live screen: 80.53 elec, 80.00 mech → 0.65% → Fail
        r = self._run(elec_vol=80.53, mech_vol=80.00)
        self.assertEqual(r["check_b_status"], "fail")

    def test_check_b_warning_l5(self):
        # L5 from live screen: 50.24 elec, 50.00 mech → 0.48% → Warning
        r = self._run(elec_vol=50.24, mech_vol=50.00, rate=242.90, product_code="FUEL-AGO")
        self.assertEqual(r["check_b_status"], "warning")

    def test_check_b_critical_locks_pump(self):
        # 1.5% divergence → Critical → pump locked
        r = self._run(elec_vol=1000, mech_vol=985.0)
        self.assertEqual(r["check_b_status"], "critical")

    def test_zero_sales_no_crash(self):
        r = self._run(elec_vol=0.0, elec_cash=0.0, mech_vol=0.0)
        self.assertEqual(r["check_b_divergence_pct"], 0.0)
        self.assertEqual(r["check_b_status"], "pass")
```

### 20.2 Unit Tests — Wetstock Formula

```python
# fms/tests/test_wetstock.py
from odoo.tests.common import TransactionCase

class TestWetstockFormula(TransactionCase):

    def _compute(self, opening, deliveries, sales, actual):
        theoretical = opening + deliveries - sales
        variance_l = theoretical - actual
        denom = opening + deliveries
        pct = (variance_l / denom * 100) if denom else 0.0
        abs_pct = abs(pct)
        if variance_l < 0 and abs_pct > 0.50:   cl = "critical"
        elif variance_l < 0 and abs_pct > 0.30: cl = "elevated"
        elif variance_l > 0 and abs_pct > 0.30: cl = "gain"
        else:                                   cl = "normal"
        return {"theoretical": theoretical, "variance_l": variance_l,
                "variance_pct": round(pct, 4), "classification": cl}

    def test_balanced_shift(self):
        r = self._compute(5000, 0, 250, 4750)
        self.assertAlmostEqual(r["variance_l"], 0.0)
        self.assertEqual(r["classification"], "normal")

    def test_critical_loss(self):
        r = self._compute(5000, 0, 250, 4710)
        self.assertGreater(abs(r["variance_pct"]), 0.5)
        self.assertEqual(r["classification"], "critical")

    def test_delivery_included(self):
        r = self._compute(5000, 8000, 1750, 11240)
        self.assertAlmostEqual(r["theoretical"], 11250.0)

    def test_maanzoni_ux_reference(self):
        r = self._compute(7000, 0, 955.99, 6040)
        self.assertEqual(r["classification"], "normal")

    def test_maanzoni_dx_reference(self):
        r = self._compute(12000, 0, 1702.44, 10290)
        self.assertEqual(r["classification"], "normal")
```

### 20.3 Unit Tests — Calibration Chart

Same interpolation logic and assertions as the ERPNext version, expressed as a plain Python test (no DB dependency needed for pure interpolation math).

### 20.4 UAT Checklist (Per Site Go-Live)

Identical checklist content to the ERPNext guide (manual workflow, PTS-2 workflow, Kenya compliance) — see Appendix A in §22 for the full checklist, with model names updated to Odoo equivalents (`fms.shift`, `fms.meter.reading`, etc.).

---

## 21. Known Limitations

**Sub-100ms pump authorisation.** Odoo's HTTP request latency (similar order of magnitude to Frappe, 50–300ms depending on worker load) is fine for shift reconciliation but not for prepay flows. Use PTS-2's local OPT integration for prepay, same as the ERPNext guide's recommendation.

**Custom SQL reports.** Odoo record rules don't filter raw `cr.execute()` queries. Every FMS SQL report must include an explicit company filter (§16, §27.2).

**AVCO and delivery variance.** The vendor bill must match the picking's received quantity (dip-measured), not docket quantity, to keep average cost consistent — Odoo enforces 3-way matching (PO/Receipt/Bill) by default; FMS must override the receipt quantity to the dip-measured value *before* the vendor bill is created, exactly mirroring the ERPNext WAC caveat.

**N/A attendant.** The legacy system accepts blank/N/A attendants. The Odoo FMS blocks `pos.order` payment confirmation without a valid `fms_pump_attendant_id` (§8.1). This is intentional — the legacy gap is eliminated.

**Odoo upgrade risk.** Custom fields and models added by the `fms` addon are preserved across Odoo version upgrades only if the addon itself is migrated (Odoo's official upgrade service, or OpenUpgrade for self-hosted migrations, handles core-to-core changes — custom addon code must be tested against the new Odoo API on staging before production, the same discipline as ERPNext's `bench update --pull --patch --build` on staging first).

**No native external WebSocket server.** As discussed in §10.5, Odoo's `bus.bus` is for pushing to Odoo's own browser sessions, not for terminating third-party device connections. Real-time pump-status streaming requires either the HTTP-command pattern (sufficient for Phases 1–2) or a small bridge sidecar (Phase 3) — there is no zero-extra-component equivalent of Frappe's native `frappe.ws` server for this specific use case.

---

## 22. Appendix

### A. Daily Operating Checklist

(Content unchanged from the legacy/ERPNext checklist — model names below refer to the Odoo `fms` addon.)

**Shift Opening (Incoming Cashier + Supervisor):**
```
□  Previous shift = Closed (or Disputed with explanation)
□  Create fms.shift: date, label, cashier(s), supervisor, EPRA rates locked
□  Create fms.cashier.session(s); issue floats → fms.cash.event: Float Issued (supervisor signs)
□  Opening dip — EVERY active tank:
     □  Tank 1 (V-Power)  □  Tank 2 (Unleaded)  □  Tank 3 (Diesel)
     □  Water levels — alert if > 20mm
□  Opening meter readings — EVERY active nozzle, ALL THREE TYPES:
     □  UX pumps: Elec Vol / Elec Cash / Man Mech
     □  DX pumps: Elec Vol / Elec Cash / Man Mech
     □  VP pumps: Elec Vol / Elec Cash / Man Mech
□  Transition → Readings Captured → Open
□  Brief attendants: do not dispense until system shows Open
```

**During the Shift:**
```
□  All POS: correct payment method + named attendant (never N/A or blank)
□  Fleet/credit → Customer Invoice (not POS) — this feeds Invoices column in cash rec
□  Till > KES 30,000: Cash Pickup + supervisor sign + envelope no. → Pymts column
□  Fuel delivery: Dip Before → wait 15 min → Dip After → Receipt + Vendor Bill
□  Drive-off: Drive-Off Record with manager authorisation
```

**Shift Closing (Cashier + Supervisor):**
```
□  Each cashier physically counts till
□  Closing meter readings — EVERY active nozzle, ALL THREE TYPES
□  Closing dip — every active tank
□  Each cashier enters actual cash count in Cashier Session
□  Enter non-cash totals per cashier: Invoices / POS / VISA (matching paper sheet columns)
□  Status → Closing
□  Run Meter Validation (Close Shift wizard) → resolve any Check B Fail/Critical
□  Compute Reconciliation → review per-cashier summaries + wetstock
□  If balanced: Approve → Post Journal Entry → Status → Closed
□  If Critical: Status → Disputed → investigate
□  Brief incoming shift
```

### B. Variance Tolerance Quick Reference

| Metric | Normal | Elevated | Critical |
|---|---|---|---|
| Wetstock loss % | ≤ 0.3% | 0.3–0.5% | > 0.5% |
| Wetstock gain | — | Any > 0.3% | — |
| Delivery dip vs docket | ≤ 0.3% | 0.3–0.5% | > 0.5% |
| Cash variance (KES) | ≤ 50 | 50–200 | > 200 |
| Meter Check A (KES) | ≤ 5 | 5–20 | > 20 |
| Meter Check B (%) | ≤ 0.30% | 0.30–0.50% | > 0.50%; > 1.0% = lock pump |

### C. PTS-2 Field Mapping

| PTS-2 Field | Odoo / FMS Field | Model |
|---|---|---|
| `DeviceId` | Lookup → `fms.pts2.device.device_id` | fms.pts2.device |
| `PumpNumber` | Resolved via `fms.pump.configuration` | fms.pump.configuration |
| `FuelGradeId` | Mapped → `fuel_grade` (product) | fms.forecourt.transaction |
| `SaleEnd` | `posting_datetime` | fms.forecourt.transaction |
| `Volume` | `quantity_litres` | fms.forecourt.transaction |
| `TotalizerVolume` | `meter_before` | fms.forecourt.transaction |
| `TransactionNumber` | `pts_transaction_number` (dedup key) | fms.forecourt.transaction |
| `Tag` | Resolved → `hr.employee` via `fms_rfid_tag_id` | fms.cashier.session |
| `TankNumber` | Mapped → `stock.location` via `fms_pts2_tank_number` | fms.tank.dip.reading |
| `ProductHeight` | `dip_height_mm` | fms.tank.dip.reading |
| `ProductVolume` | `volume_observed_l` | fms.tank.dip.reading |
| `AlertType` | `alert_type` | fms.forecourt.alert |

### D. Odoo Command Reference

```bash
# Installation
odoo-bin scaffold fms /path/to/addons
odoo-bin -d shell_maanzoni -i fms --stop-after-init
odoo-bin -d shell_maanzoni -u fms --stop-after-init   # upgrade after code changes
pip install pyserial pymodbus websockets odoorpc

# Configuration export/import (Odoo's nearest equivalent to fixtures)
odoo-bin -d shell_maanzoni --workers=0 shell   # opens an interactive ORM shell

# Testing
odoo-bin -d shell_maanzoni_test -i fms --test-tags fms --stop-after-init
odoo-bin -d shell_maanzoni_test --test-tags /fms:TestMeterValidation --stop-after-init

# Manual job execution (from the Odoo shell)
>>> env["fms.pts2.device"].watchdog_check_pts_devices()
>>> env["fms.shift"].send_daily_shift_summary()

# Debugging
tail -f /var/log/odoo/odoo-server.log
odoo-bin -d shell_maanzoni --log-level=debug

# Maintenance
pg_dump shell_maanzoni > backup.sql      # equivalent of bench backup
odoo-bin -d shell_maanzoni -u fms --stop-after-init  # apply addon update (test on staging first)
```

### E. Diagnostic SQL Queries

```sql
-- Open shifts (max 1 per station)
SELECT name, status, cashier_id, opened_at FROM fms_shift
WHERE status IN ('open', 'closing') ORDER BY opened_at DESC;

-- Missing closing meter readings for a shift
SELECT fp.name AS pump, pn.nozzle_number, mr.meter_type
FROM fms_pump fp
JOIN fms_pump_nozzle pn ON pn.pump_id = fp.id
LEFT JOIN fms_meter_reading mr
    ON mr.pump_id = fp.id AND mr.nozzle_number = pn.nozzle_number
   AND mr.shift_id = (SELECT id FROM fms_shift WHERE name = 'SHIFT-2026-00001')
   AND mr.reading_position = 'shift_close' AND mr.state = 'confirmed'
WHERE fp.is_active = true AND pn.is_active = true AND mr.id IS NULL;

-- Wetstock variance trend (last 30 days)
SELECT s.shift_date, tl.tank_location_id,
    ROUND(tl.variance_l::numeric, 2) AS var_l,
    ROUND(tl.variance_pct::numeric, 4) AS var_pct,
    tl.classification
FROM fms_shift_reconciliation_tank_line tl
JOIN fms_shift_reconciliation sr ON sr.id = tl.reconciliation_id
JOIN fms_shift s ON s.id = sr.shift_id
WHERE s.shift_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY s.shift_date DESC, tl.tank_location_id;

-- Per-cashier cash variance history
SELECT cashier_id, COUNT(*) AS shifts,
    ROUND(SUM(cash_over_under)::numeric, 2) AS net_variance,
    SUM(CASE WHEN cash_over_under < 0 THEN 1 ELSE 0 END) AS short_count,
    MAX(ABS(cash_over_under)) AS max_single_variance
FROM fms_shift_reconciliation_cashier_line
GROUP BY cashier_id ORDER BY ABS(SUM(cash_over_under)) DESC;

-- POS orders missing shift link (data quality check)
SELECT name, date_order, amount_total
FROM pos_order
WHERE fms_shift_id IS NULL AND state IN ('paid', 'done', 'invoiced')
ORDER BY date_order DESC LIMIT 20;
```

---

## 23. Architectural Principle — Shift as Metadata

### 23.1 The Critical Principle

**A Shift does not record actual transactions.** It is a coordination and accountability framework. All actual financial, inventory, and purchasing events live exclusively in Odoo's own apps:

| What actually happened | Where Odoo records it | Shift role |
|---|---|---|
| Fuel sold to customer | `pos.order` → `account.move` (POS accounting entry) | Linked via `fms_shift_id` field |
| Fleet/credit fuel sale | `account.move` (customer invoice) → AR → posted entry | Linked via `fms_shift_id` |
| Fuel delivered to tank | `purchase.order` → `stock.picking` → stock valuation move → vendor bill | Linked via `fms_shift_id` |
| Wetstock loss written off | `stock.quant` inventory adjustment or `stock.move` (scrap) → posted entry | Linked via `fms_shift_id` |
| Cash moved to safe | `account.move` (DR Safe / CR Till) | Linked via `fms_shift_id` |
| RTT correction | `stock.move` (internal transfer) | Linked via `fms_shift_id` |

The Shift's job is to:
1. Define the accountability period (who, when, at which station)
2. Capture the physical meter readings and dip readings that allow us to **verify** what Odoo's apps recorded
3. Group all the related Odoo documents so you can navigate from a single Shift record (via Odoo's smart buttons) to every order, picking, and journal entry it generated
4. Identify discrepancies between physical reality (meters, dips) and what the system recorded (orders, invoices)

**The reconciliation does not create the ledger — it verifies it.** When the manager approves a Shift Reconciliation and a journal entry is posted, that entry is for the **variance** (wetstock loss, cash short/over) — not for the sales revenue, which was already posted when each `pos.order` was paid/closed during the shift (Odoo posts POS accounting entries automatically per session, or per order depending on configuration).

### 23.2 Implications for Model Design

The `fms.shift.reconciliation.product.line` model does not store revenue as a manually-entered value. It is populated, when "Compute Reconciliation" is clicked, by querying `pos.order.line` and `account.move.line` linked to the shift:

```python
# Revenue comes from confirmed POS orders / invoices — not from meter readings
self.env.cr.execute("""
    SELECT pol.product_id,
           SUM(pol.qty) AS qty_litres,
           SUM(pol.price_subtotal) AS revenue
    FROM pos_order_line pol
    JOIN pos_order po ON po.id = pol.order_id
    WHERE po.fms_shift_id = %s AND po.state IN ('paid', 'done', 'invoiced')
    GROUP BY pol.product_id
""", (shift.id,))
```

The meter readings provide the **physical verification** of these totals. If Elec Cash (physical pump meter) diverges from POS totals (Check E), that is the signal that sales were dispensed but not invoiced.

### 23.3 What "Shift Close" Actually Posts

The only new accounting event at shift close is:

1. **Wetstock variance entry** — if physical dip differs from stock valuation by a material amount
2. **Cash variance entry** — if cashier's actual cash count differs from expected
3. **Safe drop entry** — cash moving from Till to Safe account

Everything else (revenue, COGS, stock deductions) was already posted in real time as each `pos.order` was paid (Odoo posts a POS session accounting entry automatically, configurable to post per-order or per-session-close) or as each picking was validated.

---

## 24. Standard Odoo Integration Patterns

### 24.1 Price Management via Odoo Pricelists

Do not build a separate "Fuel Price History" model to store the current pump price. Use Odoo's native `product.pricelist` and `product.pricelist.item`, which already handle this correctly and are first-class citizens of both the Sales and POS apps.

**Setup:**

```
Pricelist name:  "Pump Prices — Shell Maanzoni"
Currency:        KES
Selectable:      Yes (assigned to the station's POS Configuration)
Company:         Shell Maanzoni
```

Create one `product.pricelist.item` per fuel grade per site:

| Product | Pricelist | Fixed Price | Valid From |
|---|---|---|---|
| FUEL-PMS-UNL | Pump Prices — Shell Maanzoni | 214.20 | 2026-05-01 |
| FUEL-PMS-VP | Pump Prices — Shell Maanzoni | 229.00 | 2026-05-01 |
| FUEL-AGO | Pump Prices — Shell Maanzoni | 242.90 | 2026-05-01 |

When the shift opens, it reads the current `product.pricelist.item.fixed_price` for each grade and locks it into `rate_pms_unl`, `rate_pms_vp`, `rate_ago`. From that point on, the shift is immune to mid-shift price changes — the locked rate is the one used for all validations.

The station's **POS Configuration** (`pos.config.pricelist_id`) is set to the site-specific pricelist, so prices auto-fill on POS orders without manual entry — Odoo's POS app reads the pricelist live on every order line.

**Custom fields to add on `product.pricelist.item`** (via the `fms` module):

| Field | Type | Purpose |
|---|---|---|
| `fms_effective_shift` | Selection | Current / Next Shift / Scheduled |
| `fms_scheduled_effective_at` | Datetime | When this price takes effect |
| `fms_pts_push_status` | Selection | Pending / Pushed / Failed |
| `fms_approved_by_id` | Many2one res.users | Required if rate > EPRA max |
| `fms_epra_max_price` | Monetary | EPRA cap at time of this price |

### 24.2 Cashier as Employee + POS Session (no standalone Cashier model)

Instead of a standalone Cashier model, use the native `hr.employee` record with custom fields, **and** reuse Odoo's existing `pos.session`/`pos.config` cash-management features rather than re-implementing till tracking from scratch. Odoo's POS app already tracks a session's opening cash, closing cash, and per-payment-method totals (`pos.session.cash_register_balance_start`/`_end_real`, and `pos.payment` records grouped by `pos.payment.method`) — `fms.cashier.session` becomes a thin wrapper that links an `hr.employee` to their `pos.session` for the shift and adds the fields the paper reconciliation sheet needs that Odoo's POS doesn't track natively (Invoices/Receipts/Pymts columns, supervisor sign-off).

**Custom fields on `hr.employee`** (via the `fms` module):

| Field | Type | Purpose |
|---|---|---|
| `fms_rfid_tag_id` | Char | RFID card ID for PTS-2 pump authorisation |
| `fms_pts_pin` | Char (or `fields.Char` with a password widget) | Optional PIN for PTS authorisation |
| `fms_till_account_id` | Many2one account.account | The till account this cashier is responsible for |
| `fms_default_station_id` | Many2one res.company | Default station for this employee |
| `fms_is_cashier` | Boolean | Flags employee as a cashier for POS and session setup |
| `fms_is_supervisor` | Boolean | Can authorise cash events |

When an `fms.cashier.session` is created, it copies `fms_till_account_id` from the Employee record and is linked to the matching `pos.session`. This is the account debited in the journal entry at shift close for this cashier's actual cash count (§11.4).

This eliminates the need for a separate Cashier model and keeps all payroll, leave, and HR data consolidated on the Employee record — and, crucially, avoids duplicating cash-register logic Odoo's POS already does well.

### 24.3 `res.country.state` / Tags for HQ Regional Grouping

Odoo does not have a dedicated "Territory" model the way ERPNext does, but the same grouping need is met cleanly with either of two native mechanisms:

**Option 1 — `res.country.state` (if regions map to real administrative areas):**
```
Kenya
├── Nairobi County     ← assigned on each station's res.company.state_id
├── Mombasa County
└── ...
```

**Option 2 — a simple `res.partner.category`-style tag, or a lightweight custom `fms.region` model** if the regions are commercial groupings that don't map to administrative boundaries (e.g. "Nairobi Region", "Coast Region", "Rift Valley Region" as used in the original ERPNext example):

```python
class FmsRegion(models.Model):
    _name = "fms.region"
    _description = "Forecourt Region"
    name = fields.Char(required=True)
    company_ids = fields.One2many("res.company", "fms_region_id")
```

```python
class ResCompany(models.Model):
    _inherit = "res.company"
    fms_region_id = fields.Many2one("fms.region", string="Region")
```

```
fms.region: Nairobi Region
├── Shell Maanzoni      ← fms_region_id on Company
├── Shell Westlands
└── Shell Thika Road

fms.region: Coast Region
└── Shell Mombasa Road
```

HQ reports filter/group by `fms_region_id` to give regional views without depending on Odoo's geography model, which is the more direct equivalent of the original ERPNext `Territory` usage.

### 24.4 Stock Levels from Odoo's Native Inventory Reports

HQ does not need a custom stock dashboard for basic stock visibility. Odoo's built-in reports are the source of truth:

| Report | Location | What it shows |
|---|---|---|
| **Stock Valuation Report** | Inventory → Reporting → Valuation | Current litres and value per tank location |
| **Stock Moves History** | Inventory → Reporting → Moves History | Every movement: receipt in, sales out, adjustments |
| **Inventory Quantity** | Inventory → Reporting → Inventory | Filter by location group = all Maanzoni tanks |
| **Product Moves (ledger)** | open a product → Stock tab smart button | Per-product movement ledger |

For the HQ Dashboard, these are queried via `self.env["stock.quant"].read_group(...)` or `self.env.cr.execute()` — not recalculated from FMS models, exactly as the ERPNext guide recommends using ERPNext's own Stock Ledger.

---

## 25. Shift Auto-Open and Carry-Forward Logic

### 25.1 Shift Scheduling at the Station Level

`fms.site.preferences` defines the shift schedule for each station:

**Additional fields on `fms.site.preferences`:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `shift_schedule_type` | Selection | 24h / Multi-Shift | |
| `shift_start_time` | Float (time) | 6.0 | For 24h stations: daily start time |
| `shift_duration_hours` | Integer | 24 | For 24h stations |
| `shift_1_start` | Float (time) | 6.0 | For multi-shift: Shift 1 start |
| `shift_1_label` | Char | Day | |
| `shift_2_start` | Float (time) | 14.0 | Shift 2 start |
| `shift_2_label` | Char | Evening | |
| `shift_3_start` | Float (time) | 22.0 | Shift 3 start |
| `shift_3_label` | Char | Night | |
| `auto_open_next_shift` | Boolean | True | Auto-create next shift on close |
| `carry_forward_readings_on_skip` | Boolean | True | Carry forward if close skipped |

### 25.2 Auto-Open Logic

When a shift is closed, if `auto_open_next_shift = True`, the system immediately creates the next shift and populates its opening meter readings from the closed shift's closing readings.

```python
# fms/models/fms_shift_auto.py
from odoo import models, fields
from datetime import timedelta

class FmsShift(models.Model):
    _inherit = "fms.shift"

    def action_close(self):
        """Called when status transitions to 'closed' — fires auto-open."""
        res = super().action_close() if hasattr(super(), "action_close") else None
        for shift in self:
            prefs = self.env["fms.site.preferences"].search(
                [("company_id", "=", shift.company_id.id)], limit=1)
            if prefs and prefs.auto_open_next_shift:
                shift._auto_open_next_shift(prefs)
        return res

    def _auto_open_next_shift(self, prefs):
        self.ensure_one()
        next_date, next_label = self._next_shift_datetime(prefs)

        new_shift = self.create({
            "company_id": self.company_id.id,
            "station_id": self.station_id.id,
            "shift_date": next_date,
            "shift_label": next_label,
            "status": "open",
            "opened_at": fields.Datetime.now(),
            "rate_pms_unl": self._get_current_price("FUEL-PMS-UNL"),
            "rate_pms_vp": self._get_current_price("FUEL-PMS-VP"),
            "rate_ago": self._get_current_price("FUEL-AGO"),
            "rate_dpk": self._get_current_price("FUEL-DPK"),
        })

        self._carry_forward_meter_readings(new_shift)
        self._carry_forward_dip_readings(new_shift)
        return new_shift

    def _carry_forward_meter_readings(self, new_shift):
        closing = self.env["fms.meter.reading"].search([
            ("shift_id", "=", self.id), ("reading_position", "=", "shift_close"),
            ("state", "=", "confirmed"),
        ])
        for cr in closing:
            self.env["fms.meter.reading"].create({
                "shift_id": new_shift.id, "pump_id": cr.pump_id.id,
                "nozzle_number": cr.nozzle_number, "meter_type": cr.meter_type,
                "reading_position": "shift_open", "totalizer_value": cr.totalizer_value,
                "observed_at": fields.Datetime.now(),
                "notes": f"Carried forward from shift {self.name}",
                "state": "confirmed",
            })

    def _carry_forward_dip_readings(self, new_shift):
        closing_dips = self.env["fms.tank.dip.reading"].search([
            ("shift_id", "=", self.id), ("reading_type", "=", "shift_close"),
        ])
        for cd in closing_dips:
            self.env["fms.tank.dip.reading"].create({
                "shift_id": new_shift.id, "company_id": new_shift.company_id.id,
                "tank_location_id": cd.tank_location_id.id, "reading_type": "shift_open",
                "reading_source": cd.reading_source, "volume_observed_l": cd.volume_observed_l,
                "dip_height_mm": cd.dip_height_mm, "water_level_mm": cd.water_level_mm,
                "calibration_chart_id": cd.calibration_chart_id.id,
                "reading_datetime": fields.Datetime.now(),
            })

    def handle_skipped_close(self):
        """
        Called when a supervisor opens a new shift without closing the previous one.
        The previous shift's opening readings are carried forward as its own closing
        readings (system assumes nothing changed — conservative, flags for review).
        """
        self.ensure_one()
        if self.status not in ("open", "readings_captured"):
            return
        opening = self.env["fms.meter.reading"].search([
            ("shift_id", "=", self.id), ("reading_position", "=", "shift_open"),
            ("state", "=", "confirmed"),
        ])
        for om in opening:
            exists = self.env["fms.meter.reading"].search([
                ("shift_id", "=", self.id), ("pump_id", "=", om.pump_id.id),
                ("nozzle_number", "=", om.nozzle_number), ("meter_type", "=", om.meter_type),
                ("reading_position", "=", "shift_close"),
            ], limit=1)
            if not exists:
                self.env["fms.meter.reading"].create({
                    "shift_id": self.id, "pump_id": om.pump_id.id,
                    "nozzle_number": om.nozzle_number, "meter_type": om.meter_type,
                    "reading_position": "shift_close", "totalizer_value": om.totalizer_value,
                    "observed_at": fields.Datetime.now(),
                    "notes": "AUTO: Closing assumed same as opening — shift close was skipped",
                    "state": "confirmed",
                })
        self.message_post(body=(
            f"Shift {self.name} was not formally closed. Closing readings have been set "
            f"equal to opening readings (zero sales assumed). Review this shift's "
            f"reconciliation before approving."))

    def _get_current_price(self, product_code):
        product = self.env["product.product"].search(
            [("default_code", "=", product_code)], limit=1)
        pos_config = self.env["pos.config"].search(
            [("company_id", "=", self.company_id.id)], limit=1)
        pricelist = pos_config.pricelist_id
        if not pricelist or not product:
            return 0.0
        item = self.env["product.pricelist.item"].search([
            ("pricelist_id", "=", pricelist.id), ("product_id", "=", product.id),
            ("fms_effective_shift", "in", ("current", False)),
        ], order="date_start desc", limit=1)
        return item.fixed_price if item else 0.0

    def _next_shift_datetime(self, prefs):
        if prefs.shift_schedule_type == "24h":
            return self.shift_date + timedelta(days=1), "Day"
        labels = [l for l in (prefs.shift_1_label, prefs.shift_2_label, prefs.shift_3_label) if l]
        try:
            idx = labels.index(self.shift_label)
            if idx + 1 < len(labels):
                return self.shift_date, labels[idx + 1]
            return self.shift_date + timedelta(days=1), labels[0]
        except ValueError:
            return self.shift_date + timedelta(days=1), labels[0] if labels else "Day"
```

### 25.3 Meter Reading Organisation on the Shift Form

Opening meter readings are displayed as an editable `one2many` list (`tree`/`list` view embedded in the `fms.shift` form), grouped by pump and nozzle, with all three types side by side via a custom widget or a grouped list view. Once confirmed (carried forward or manually entered), the rows become read-only (`readonly="state == 'confirmed'"` domain on the embedded tree).

```
┌──────────────────────────────────────────────────────────────────┐
│  OPENING METER READINGS (Read-Only after confirmation)            │
├──────────┬──────────┬──────────────────────────────────────────┤
│  Pump    │  Nozzle  │  Elec Vol (L)   Elec Cash (KES)  Man Mech│
├──────────┼──────────┼──────────────────────────────────────────┤
│  UX5     │  2 (UX)  │  171,275,183  │  29,387,277  │  171,275,182│
│  UX6     │  2 (UX)  │  462,357.45   │  99,034,978  │  462,357.4 │
│  DX5     │  1 (DX)  │  55,065,556   │  15,918,476  │  55,065,556│
│  VP7     │  1 (VP)  │  9,884,632    │   2,263,540  │   9,884,632│
│  ...     │  ...     │  ...          │  ...         │  ...       │
└──────────┴──────────┴──────────────────────────────────────────┘

  CLOSING METER READINGS (Editable until shift closes)
  [Enter values here — system validates against opening]
```

The closing readings section is an editable mirror of the same structure, with computed (non-stored, `compute` with no `store=True`) "delta" fields (Sold Ltrs, Sold KES, Var Ltrs) displayed in real time as the supervisor types — exactly like the legacy screen's `VIEW THROUGHPUT AND SALES FOR FUEL PUMPS` section, and identical in spirit to the ERPNext form layout.

---

## 26. HQ Configuration Powers

### 26.1 What HQ Can Configure (Not Just Read)

HQ Manager has read access to all financial data across companies (via `Allowed Companies` on their user). In addition, HQ Manager has **configuration rights** over sub-company settings — not to edit transactions, but to manage master data that drives how the stations operate.

| Action | Where | Who |
|---|---|---|
| Set EPRA pump prices for any site | `product.pricelist.item` (with `fms_effective_shift`) | HQ Manager |
| Schedule bulk price change across all sites | Bulk Price Update wizard | HQ Manager |
| Configure Site Preferences for any site | `fms.site.preferences` | HQ Manager |
| Create/edit Pump and Nozzle master data | `fms.pump`, `fms.pump.nozzle` | HQ Manager |
| Create/edit Tank Calibration Charts for any site | `fms.tank.calibration.chart` | HQ Manager |
| Add/deactivate employees for any site | `hr.employee` | HQ Manager |
| Set multi-company access for site staff | `res.users.company_ids` | HQ Manager |
| View but NOT edit confirmed transactions | All Odoo models | HQ Manager (read-only via `ir.model.access.csv` row with `perm_write = 0`) |

Enforced via Odoo's **Access Rights** (`ir.model.access.csv`) and **Record Rules**:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_fms_shift_hq_manager,fms.shift.hq.manager,model_fms_shift,fms.group_hq_manager,1,0,0,0
access_pricelist_item_hq_manager,pricelist.item.hq.manager,product.model_product_pricelist_item,fms.group_hq_manager,1,1,1,0
access_site_prefs_hq_manager,site.prefs.hq.manager,model_fms_site_preferences,fms.group_hq_manager,1,1,0,0
access_pos_order_hq_manager,pos.order.hq.manager,point_of_sale.model_pos_order,fms.group_hq_manager,1,0,0,0
access_account_move_hq_manager,account.move.hq.manager,account.model_account_move,fms.group_hq_manager,1,0,0,0
```

### 26.2 Bulk Price Change with Scheduled Effective Shift

HQ Manager opens the **Bulk Price Update** wizard (a `TransientModel` with a form view, the Odoo equivalent of ERPNext's custom Page):

1. Select fuel grades to update (Many2many checkboxes: UX, VP, DX, DPK)
2. Enter new prices for each grade
3. Select sites to apply to (Many2many companies, "Select All" available)
4. Set effectiveness: `Immediately` or `Next Shift` (default) or `Scheduled: [datetime]`
5. Enter EPRA gazette reference
6. Click **Apply**

```python
# fms/wizards/fms_bulk_price_update_wizard.py
from odoo import models, fields, api
from odoo.exceptions import UserError

class FmsBulkPriceUpdateWizard(models.TransientModel):
    _name = "fms.bulk.price.update.wizard"
    _description = "Bulk Pump Price Update"

    product_ids = fields.Many2many("product.product", domain=[("fms_is_fuel_product", "=", True)])
    new_price = fields.Float()
    company_ids = fields.Many2many("res.company")
    effective = fields.Selection([
        ("immediate", "Immediately"), ("next_shift", "Next Shift"),
        ("scheduled", "Scheduled")], default="next_shift")
    scheduled_at = fields.Datetime()
    epra_reference = fields.Char(string="EPRA Gazette Reference")

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("fms.group_hq_manager"):
            raise UserError("Insufficient permissions for price update.")

        created = []
        for company in self.company_ids:
            pos_config = self.env["pos.config"].search(
                [("company_id", "=", company.id)], limit=1)
            pricelist = pos_config.pricelist_id
            if not pricelist:
                self.env["ir.logging"].create({
                    "name": "fms.bulk_price", "type": "server", "level": "WARNING",
                    "message": f"No pricelist found for {company.name}",
                    "path": "fms", "line": "0", "func": "action_apply"})
                continue

            for product in self.product_ids:
                current = self.env["product.pricelist.item"].search([
                    ("pricelist_id", "=", pricelist.id), ("product_id", "=", product.id),
                    ("fms_effective_shift", "=", "current"),
                ], limit=1)
                epra_max = current.fms_epra_max_price if current else 0.0

                if epra_max and self.new_price > epra_max:
                    raise UserError(
                        f"{product.display_name} at {company.name}: new price "
                        f"{self.new_price} exceeds EPRA cap {epra_max}. Add EPRA gazette "
                        f"reference and approval.")

                item = self.env["product.pricelist.item"].create({
                    "pricelist_id": pricelist.id, "product_id": product.id,
                    "compute_price": "fixed", "fixed_price": self.new_price,
                    "date_start": fields.Date.today(),
                    "fms_effective_shift": {
                        "immediate": "current", "next_shift": "next_shift",
                        "scheduled": "scheduled"}[self.effective],
                    "fms_scheduled_effective_at": self.scheduled_at,
                    "fms_epra_max_price": epra_max,
                    "fms_approved_by_id": self.env.user.id,
                })

                if self.effective == "immediate":
                    device = self.env["fms.pts2.device"].search(
                        [("company_id", "=", company.id)], limit=1)
                    if device:
                        self.env["fms.pts2.commands"].push_price_update(
                            device, [{"id": product.fms_pts2_grade_id, "price": str(self.new_price)}])

                created.append((company.name, product.display_name, self.new_price))

        return {"type": "ir.actions.act_window_close"}
```

---

## 27. Reporting Suite

### 27.1 Core Odoo Reports Used Directly (No Customisation Needed)

These native Odoo reports work out of the box and are the primary financial data sources for both HQ and station managers:

**Stock / Inventory:**

| Report | Path | FMS Use |
|---|---|---|
| Stock Valuation Report | Inventory → Reporting → Valuation | Current litres and value per tank location |
| Moves History | Inventory → Reporting → Moves History | Every stock movement with before/after qty |
| Inventory Report (Quants) | Inventory → Reporting → Inventory | All tanks at a glance, filter by location |
| Product Moves Ledger | Product → Stock tab → Moves | Per-delivery, per-grade movement tracking |

**Sales / Revenue:**

| Report | Path | FMS Use |
|---|---|---|
| Invoice Analysis | Accounting → Reporting → Invoice Analysis | All invoices by date, customer, product |
| Sales Analysis (POS) | Point of Sale → Reporting → Orders | Volume and revenue per fuel grade |
| Session Report | POS → Orders → Sessions | Per-cashier, per-payment-method breakdown |
| Sales Pivot/Graph | Sales → Reporting | Revenue trend over time |
| Customer Statement | Accounting → Customers → a customer → Statement | Fleet account spend |

**Purchasing:**

| Report | Path | FMS Use |
|---|---|---|
| Purchase Analysis | Purchase → Reporting | All receipts by date and supplier |
| Vendor Bills Analysis | Accounting → Reporting → Vendor Bill Analysis | Litres received per grade (via bill lines) |

**Finance / GL:**

| Report | Path | FMS Use |
|---|---|---|
| General Ledger | Accounting → Reporting → General Ledger | All entries — filter by account or analytic account |
| Trial Balance | Accounting → Reporting → Trial Balance | Station-level snapshot |
| Profit and Loss | Accounting → Reporting → Profit and Loss | Revenue vs COGS per station (filter by company) |
| Cash Flow Statement | Accounting → Reporting → Cash Flow Statement | Cash position |
| Aged Receivable | Accounting → Reporting → Partner Ledger / Aged Receivable | Outstanding fleet invoices |

### 27.2 Custom FMS Reports (Python Models + QWeb/List Views)

Odoo doesn't have a direct "Script Report" concept identical to Frappe's; the closest idiomatic equivalents are: (a) a regular Odoo model backed by a SQL view or a `read_group`/raw-SQL Python method, exposed through a normal list/pivot view, or (b) a QWeb report for printable output. FMS uses option (a) for all analytical reports below — each is a thin, mostly-readonly Odoo model (`_auto = False`, backed by a SQL `VIEW`) which is the standard Odoo pattern for "reporting models".

#### 27.2.1 Daily Shift Summary Report

Mirrors the current legacy system's output. One row per shift. Implemented as an SQL-view-backed model (`_auto = False`) for fast, filterable, exportable list/pivot views in the UI — the Odoo-idiomatic alternative to a Frappe Script Report.

```python
# fms/report/fms_daily_shift_summary.py
from odoo import models, fields, tools

class FmsDailyShiftSummary(models.Model):
    _name = "fms.daily.shift.summary"
    _description = "Daily Shift Summary"
    _auto = False
    _order = "shift_date desc"

    shift_date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    shift_label = fields.Char(readonly=True)
    cashier_id = fields.Many2one("hr.employee", readonly=True)
    ux_vol = fields.Float(readonly=True)
    ux_revenue = fields.Monetary(readonly=True)
    vp_vol = fields.Float(readonly=True)
    dx_vol = fields.Float(readonly=True)
    dx_revenue = fields.Monetary(readonly=True)
    total_revenue = fields.Monetary(readonly=True)
    cash_variance = fields.Monetary(readonly=True)
    wetstock_var = fields.Float(readonly=True)
    status = fields.Char(readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    s.id AS id,
                    s.shift_date AS shift_date, s.company_id AS company_id,
                    s.shift_label AS shift_label, s.cashier_id AS cashier_id,
                    COALESCE(SUM(CASE WHEN p.default_code = 'FUEL-PMS-UNL' THEN pol.qty END), 0) AS ux_vol,
                    COALESCE(SUM(CASE WHEN p.default_code = 'FUEL-PMS-UNL' THEN pol.price_subtotal END), 0) AS ux_revenue,
                    COALESCE(SUM(CASE WHEN p.default_code = 'FUEL-PMS-VP' THEN pol.qty END), 0) AS vp_vol,
                    COALESCE(SUM(CASE WHEN p.default_code = 'FUEL-AGO' THEN pol.qty END), 0) AS dx_vol,
                    COALESCE(SUM(CASE WHEN p.default_code = 'FUEL-AGO' THEN pol.price_subtotal END), 0) AS dx_revenue,
                    COALESCE(SUM(pol.price_subtotal), 0) AS total_revenue,
                    sr.cash_variance AS cash_variance,
                    sr.wetstock_variance_l AS wetstock_var,
                    s.status AS status,
                    c.currency_id AS currency_id
                FROM fms_shift s
                JOIN res_company c ON c.id = s.company_id
                LEFT JOIN pos_order po ON po.fms_shift_id = s.id AND po.state IN ('paid','done','invoiced')
                LEFT JOIN pos_order_line pol ON pol.order_id = po.id
                LEFT JOIN product_product pp ON pp.id = pol.product_id
                LEFT JOIN product_template p ON p.id = pp.product_tmpl_id
                LEFT JOIN fms_shift_reconciliation sr ON sr.shift_id = s.id
                GROUP BY s.id, s.shift_date, s.company_id, s.shift_label, s.cashier_id,
                         sr.cash_variance, sr.wetstock_variance_l, s.status, c.currency_id
            )
        """)
```

#### 27.2.2 Per-Cashier Cash Reconciliation Report

Replicates the current paper Cash Reconciliation Sheet. Because this report is always scoped to one shift at a time and needs a totals row, it is implemented as a plain (non-SQL-view) transient computation surfaced in the `fms.shift.reconciliation` form's cashier-lines tab rather than a separate reporting model — the lines already exist as `fms.shift.reconciliation.cashier.line` records (§7.10); the "report" is simply that list view plus a computed totals footer, which Odoo's list views render natively via `sum` aggregates declared in the view XML:

```xml
<list>
    <field name="cashier_id"/>
    <field name="sales" sum="Total Sales"/>
    <field name="invoices" sum="Total Invoices"/>
    <field name="pos_payments" sum="Total POS"/>
    <field name="visa_card" sum="Total VISA"/>
    <field name="total_credits" sum="Total Credits"/>
    <field name="receipts" sum="Total Receipts"/>
    <field name="payments_out" sum="Total Pymts"/>
    <field name="expected_cash" sum="Total Expected"/>
    <field name="actual_cash" sum="Total Actual"/>
    <field name="cash_over_under" sum="Total Over/(Under)"/>
</list>
```

This is, in practice, simpler than the ERPNext Script Report equivalent because Odoo list-view column sums are declarative.

#### 27.2.3 Wetstock Variance Trend Report

```python
# fms/report/fms_wetstock_variance_trend.py
QUERY = """
SELECT
    s.id AS id,
    s.shift_date, s.company_id AS station_id,
    tl.tank_location_id, tl.fuel_product_id,
    ROUND(tl.opening_stock_l::numeric, 1)       AS opening_l,
    ROUND(tl.deliveries_l::numeric, 1)          AS deliveries_l,
    ROUND(tl.elec_vol_sales_l::numeric, 3)      AS sales_l,
    ROUND(tl.theoretical_closing_l::numeric, 1) AS theoretical_l,
    ROUND(tl.actual_closing_l::numeric, 1)      AS actual_l,
    ROUND(tl.variance_l::numeric, 2)            AS variance_l,
    ROUND(tl.variance_pct::numeric, 4)          AS variance_pct,
    tl.classification,
    ROUND(tl.variance_kes::numeric, 2)          AS variance_kes
FROM fms_shift_reconciliation_tank_line tl
JOIN fms_shift_reconciliation sr ON sr.id = tl.reconciliation_id
JOIN fms_shift s ON s.id = sr.shift_id
WHERE s.shift_date BETWEEN %(from_date)s AND %(to_date)s
  AND (%(company_id)s IS NULL OR s.company_id = %(company_id)s)
ORDER BY s.shift_date DESC, tl.tank_location_id
"""
```

#### 27.2.4 Meter Reading Discrepancy Log

```sql
SELECT
    s.id AS id,
    s.shift_date, s.company_id AS station_id,
    mvr.pump_id, mvr.nozzle_number,
    ROUND(mvr.elec_vol_sold::numeric, 3) AS elec_vol_l,
    ROUND(mvr.mech_vol_sold::numeric, 1) AS mech_vol_l,
    ROUND(mvr.check_b_divergence_pct::numeric, 4) AS divergence_pct,
    mvr.check_b_status, mvr.check_a_status, mvr.overall_status
FROM fms_meter_validation_result mvr
JOIN fms_shift s ON s.id = mvr.shift_id
WHERE s.shift_date BETWEEN %(from_date)s AND %(to_date)s
  AND mvr.check_b_status != 'pass'
ORDER BY s.shift_date DESC, mvr.check_b_divergence_pct DESC
```

#### 27.2.5 Delivery Reconciliation Register

```sql
SELECT
    fdd.id AS id,
    sp.scheduled_date AS date, s.company_id AS station_id,
    fdd.truck_reg, fdd.docket_number, fdd.fuel_product_id,
    ROUND(fdd.docket_volume_l::numeric, 1) AS docket_l,
    ROUND(fdd.dip_measured_l::numeric, 1)  AS received_l,
    ROUND(fdd.delivery_variance_l::numeric, 2) AS variance_l,
    ROUND(fdd.delivery_variance_pct::numeric, 3) AS variance_pct,
    fdd.state, fdd.picking_id
FROM fms_fuel_delivery_dip fdd
JOIN fms_shift s ON s.id = fdd.shift_id
LEFT JOIN stock_picking sp ON sp.id = fdd.picking_id
WHERE sp.scheduled_date BETWEEN %(from_date)s AND %(to_date)s
  AND (%(company_id)s IS NULL OR s.company_id = %(company_id)s)
ORDER BY sp.scheduled_date DESC
```

#### 27.2.6 Cashier Performance Summary

```sql
SELECT
    cl.cashier_id AS id,
    COUNT(DISTINCT sr.shift_id) AS shift_count,
    ROUND(SUM(cl.sales)::numeric, 2) AS total_sales,
    ROUND(SUM(cl.actual_cash)::numeric, 2) AS total_cash_handled,
    ROUND(SUM(cl.cash_over_under)::numeric, 2) AS net_variance,
    ROUND(AVG(cl.cash_over_under)::numeric, 2) AS avg_per_shift,
    SUM(CASE WHEN cl.cash_over_under < 0 THEN 1 ELSE 0 END) AS short_count,
    SUM(CASE WHEN cl.cash_over_under > 0 THEN 1 ELSE 0 END) AS over_count,
    ROUND(MAX(ABS(cl.cash_over_under))::numeric, 2) AS largest_variance
FROM fms_shift_reconciliation_cashier_line cl
JOIN fms_shift_reconciliation sr ON sr.id = cl.reconciliation_id
JOIN fms_shift s ON s.id = sr.shift_id
WHERE s.shift_date BETWEEN %(from_date)s AND %(to_date)s
  AND (%(company_id)s IS NULL OR s.company_id = %(company_id)s)
GROUP BY cl.cashier_id
ORDER BY ABS(SUM(cl.cash_over_under)) DESC
```

---

## 28. HQ Dashboard

### 28.1 HQ Dashboard Design

The HQ Dashboard uses Odoo's native **Dashboards/Spreadsheet Dashboard** app (Enterprise) if available, or a custom OWL-based dashboard view (Community-compatible) registered as an `ir.actions.client` action inside the `fms` module — the equivalent of ERPNext's Frappe Dashboard + Dashboard Chart records.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SHELL KENYA HQ — FORECOURT DASHBOARD                  Today: 25 May 2026│
├───────────────────────────────┬─────────────────────────────────────────┤
│  FUEL STOCK — ALL SITES        │  TODAY'S REVENUE — BY SITE              │
│                                │                                         │
│  [Stacked Bar: litres per      │  [Bar Chart: KES revenue per company,   │
│   tank per company]            │   colour by product grade]              │
│                                │                                         │
│  Tank 2 UX — Maanzoni: 5,268 L │  Maanzoni:    KES 619,312              │
│  Tank 3 DX — Maanzoni: 10,240 L│  Mombasa Rd:  KES 412,500              │
│  Tank 2 UX — Westlands: 3,100 L│  Westlands:   KES 390,200              │
├───────────────────────────────┼─────────────────────────────────────────┤
│  OPEN SHIFTS                   │  CASH VARIANCE — LAST 7 DAYS            │
│                                │                                         │
│  ● Maanzoni — Day — OPEN       │  [Line chart per cashier, KES]          │
│  ● Mombasa — Day — OPEN        │  Swedi:   ▼ (1,100) yesterday          │
│  ● Westlands — CLOSED          │  Peter:   △ 116.50 yesterday           │
│  ● Thika — Disputed ⚠️          │  Joseph:  △ 0.77 yesterday            │
├───────────────────────────────┼─────────────────────────────────────────┤
│  WETSTOCK ALERTS               │  METER CHECK B — RECENT FAILS           │
│                                │                                         │
│  ⚠️ Mombasa Tank 2: 0.6% loss  │  ⚠️ U7 — Maanzoni: 0.65% (Fail)       │
│  ✅ Maanzoni: all normal       │  ⚠️ L5 — Maanzoni: 0.48% (Warning)    │
│  ⚠️ Thika: delivery disputed   │  ✅ All others: Pass                    │
└───────────────────────────────┴─────────────────────────────────────────┘
```

### 28.2 Dashboard Data Methods (Python)

```python
# fms/models/fms_dashboard.py
from odoo import models, fields, api

class FmsDashboard(models.AbstractModel):
    _name = "fms.dashboard"
    _description = "FMS HQ Dashboard Data Provider"

    @api.model
    def get_fuel_stock_by_site(self):
        """
        Returns current stock levels per tank per company.
        Reads from Odoo's stock.quant — the source of truth.
        """
        self.env.cr.execute("""
            SELECT
                l.company_id, l.id AS location_id, l.fms_fuel_product_id AS product_id,
                COALESCE(SUM(q.quantity), 0) AS qty_litres,
                l.fms_capacity_litres AS capacity
            FROM stock_location l
            LEFT JOIN stock_quant q
                ON q.location_id = l.id AND q.product_id = l.fms_fuel_product_id
            WHERE l.fms_is_fuel_tank = true
            GROUP BY l.company_id, l.id, l.fms_fuel_product_id, l.fms_capacity_litres
            ORDER BY l.company_id, l.id
        """)
        rows = self.env.cr.dictfetchall()
        for row in rows:
            cap = row["capacity"] or 0
            row["status"] = ("critical" if cap and row["qty_litres"] < cap * 0.10 else
                              "low" if cap and row["qty_litres"] < cap * 0.20 else "normal")
        return rows

    @api.model
    def get_open_shifts_status(self):
        self.env.cr.execute("""
            SELECT s.id, s.company_id, s.shift_date, s.shift_label, s.status,
                   s.opened_at, s.cashier_id,
                   EXTRACT(EPOCH FROM (NOW() - s.opened_at)) / 3600 AS hours_open
            FROM fms_shift s
            WHERE s.status IN ('open', 'closing', 'disputed')
            ORDER BY s.opened_at DESC
        """)
        return self.env.cr.dictfetchall()

    @api.model
    def get_today_revenue_by_site(self):
        self.env.cr.execute("""
            SELECT po.company_id, pol.product_id,
                   ROUND(SUM(pol.qty)::numeric, 3) AS qty_litres,
                   ROUND(SUM(pol.price_subtotal)::numeric, 2) AS revenue
            FROM pos_order_line pol
            JOIN pos_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE po.date_order::date = CURRENT_DATE
              AND po.state IN ('paid', 'done', 'invoiced')
              AND pt.fms_is_fuel_product = true
            GROUP BY po.company_id, pol.product_id
            ORDER BY po.company_id, pol.product_id
        """)
        return self.env.cr.dictfetchall()

    @api.model
    def get_wetstock_alerts(self):
        self.env.cr.execute("""
            SELECT s.company_id, s.shift_date, tl.tank_location_id, tl.fuel_product_id,
                   ROUND(tl.variance_l::numeric, 2) AS variance_l,
                   ROUND(tl.variance_pct::numeric, 4) AS variance_pct, tl.classification
            FROM fms_shift_reconciliation_tank_line tl
            JOIN fms_shift_reconciliation sr ON sr.id = tl.reconciliation_id
            JOIN fms_shift s ON s.id = sr.shift_id
            WHERE tl.classification IN ('elevated', 'critical', 'gain')
              AND s.shift_date >= CURRENT_DATE - INTERVAL '2 days'
            ORDER BY s.shift_date DESC, tl.classification DESC
        """)
        return self.env.cr.dictfetchall()
```

### 28.3 Dashboard Client Action

Rather than ERPNext's declarative `Dashboard`/`Dashboard Chart` doctype JSON, Odoo's idiomatic approach for a fully custom multi-widget dashboard is a small **OWL component** registered as a client action, calling the methods in §28.2 via `this.orm.call("fms.dashboard", "get_fuel_stock_by_site", [])`. If Odoo Enterprise is available, the **Spreadsheet Dashboard** app is a lower-code alternative: each chart is built as a pivot/graph view on the reporting models from §27.2 and pinned to a dashboard, closer in spirit (and effort) to ERPNext's point-and-click Dashboard Chart records.

```javascript
// fms/static/src/js/fms_dashboard.js
/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FmsHqDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({ stock: [], shifts: [], revenue: [], alerts: [] });
        onWillStart(async () => {
            this.state.stock = await this.orm.call("fms.dashboard", "get_fuel_stock_by_site", []);
            this.state.shifts = await this.orm.call("fms.dashboard", "get_open_shifts_status", []);
            this.state.revenue = await this.orm.call("fms.dashboard", "get_today_revenue_by_site", []);
            this.state.alerts = await this.orm.call("fms.dashboard", "get_wetstock_alerts", []);
        });
    }
}
FmsHqDashboard.template = "fms.HqDashboard";
registry.category("actions").add("fms_hq_dashboard", FmsHqDashboard);
```

### 28.4 Per-Region Stock View

```python
@api.model
def get_stock_by_region(self):
    """Group fuel stock by fms.region for regional HQ view."""
    self.env.cr.execute("""
        SELECT r.name AS region, l.company_id, l.fms_fuel_product_id AS product_id,
               COALESCE(SUM(q.quantity), 0) AS qty_litres, l.fms_capacity_litres AS capacity
        FROM stock_location l
        JOIN res_company c ON c.id = l.company_id
        LEFT JOIN fms_region r ON r.id = c.fms_region_id
        LEFT JOIN stock_quant q ON q.location_id = l.id AND q.product_id = l.fms_fuel_product_id
        WHERE l.fms_is_fuel_tank = true
        GROUP BY r.name, l.company_id, l.fms_fuel_product_id, l.fms_capacity_litres
        ORDER BY r.name, l.company_id
    """)
    return self.env.cr.dictfetchall()
```

---

## 29. Backend Menus & Dashboards

### 29.1 Station Backend Menu

Odoo organises navigation through `ir.ui.menu` + `ir.actions.act_window` records, grouped per app. There is no exact equivalent to ERPNext's drag-and-drop "Workspace" builder; the closest like-for-like is a top-level Odoo app menu (`Forecourt Station`) with sub-menus and a dashboard kanban/list landing action — functionally identical to ERPNext's Workspace cards once built.

**Station Menu — Site Cashier / Supervisor:**

```
┌─────────────────────────────────────────────────────────────────┐
│  SHELL MAANZONI — FORECOURT STATION                             │
├──────────────────────────────────────────────────────────────────┤
│  QUICK LINKS (top app menu items)                                │
│                                                                  │
│  [Open Shift]   [Meter Reading]   [Dip Reading]   [POS Order]   │
│  [Cash Event]   [Fuel Delivery]   [Drive-Off]     [View Shift]  │
├──────────────────────────────────────────────────────────────────┤
│  TODAY'S SHIFT STATUS  (kanban/dashboard landing view)           │
│                                                                  │
│  Shift: SHIFT-2026-00142  Status: OPEN  Since: 06:00            │
│  Cashiers on duty: Swedi Abuti, Peter Mbeve, Joseph Matale       │
│  Meter readings: ✅ Opening done   Closing: pending              │
│  Dip readings:   ✅ Opening done   Closing: pending              │
├──────────────────────────────────────────────────────────────────┤
│  ALERTS (chatter / activity feed on the shift record)            │
│  ⚠️ U7 Pump: Meter Check B Warning (0.65%) — schedule calibration│
│  💧 No water contamination detected                             │
├──────────────────────────────────────────────────────────────────┤
│  REPORTS (station-scoped, filtered by company)                   │
│  Daily Shift Summary | Cashier Cash Reconciliation              │
│  Wetstock Variance Trend | Delivery Reconciliation Register     │
└──────────────────────────────────────────────────────────────────┘
```

**Menu definition (`fms/views/fms_menus.xml`):**

```xml
<odoo>
    <menuitem id="menu_fms_root" name="Forecourt Station" sequence="10"
              web_icon="fms,static/description/icon.png"/>

    <menuitem id="menu_fms_shift_ops" name="Shift Operations" parent="menu_fms_root" sequence="10"/>
    <menuitem id="menu_fms_shift" name="Shifts" parent="menu_fms_shift_ops"
              action="action_fms_shift" sequence="10"/>
    <menuitem id="menu_fms_meter_reading" name="Meter Readings" parent="menu_fms_shift_ops"
              action="action_fms_meter_reading" sequence="20"/>
    <menuitem id="menu_fms_dip_reading" name="Dip Readings" parent="menu_fms_shift_ops"
              action="action_fms_tank_dip_reading" sequence="30"/>
    <menuitem id="menu_fms_cashier_session" name="Cashier Sessions" parent="menu_fms_shift_ops"
              action="action_fms_cashier_session" sequence="40"/>
    <menuitem id="menu_fms_cash_event" name="Cash Events" parent="menu_fms_shift_ops"
              action="action_fms_cash_event" sequence="50"/>

    <menuitem id="menu_fms_exceptions" name="Deliveries &amp; Exceptions" parent="menu_fms_root" sequence="20"/>
    <menuitem id="menu_fms_delivery_dip" name="Fuel Deliveries" parent="menu_fms_exceptions"
              action="action_fms_fuel_delivery_dip" sequence="10"/>
    <menuitem id="menu_fms_drive_off" name="Drive-Offs" parent="menu_fms_exceptions"
              action="action_fms_drive_off_record" sequence="20"/>
    <menuitem id="menu_fms_alert" name="Forecourt Alerts" parent="menu_fms_exceptions"
              action="action_fms_forecourt_alert" sequence="30"/>
    <menuitem id="menu_fms_reconciliation" name="Shift Reconciliation" parent="menu_fms_exceptions"
              action="action_fms_shift_reconciliation" sequence="40"/>

    <menuitem id="menu_fms_reports" name="Station Reports" parent="menu_fms_root" sequence="30"/>
    <menuitem id="menu_fms_report_daily_summary" name="Daily Shift Summary" parent="menu_fms_reports"
              action="action_fms_daily_shift_summary" sequence="10"/>
    <menuitem id="menu_fms_report_wetstock_trend" name="Wetstock Variance Trend" parent="menu_fms_reports"
              action="action_fms_wetstock_variance_trend" sequence="20"/>
    <menuitem id="menu_fms_report_delivery_register" name="Delivery Reconciliation Register"
              parent="menu_fms_reports" action="action_fms_delivery_reconciliation" sequence="30"/>
</odoo>
```

### 29.2 HQ Backend Menu

```
┌─────────────────────────────────────────────────────────────────┐
│  SHELL KENYA HQ — FORECOURT MANAGEMENT                          │
├──────────────────────────────────────────────────────────────────┤
│  QUICK ACTIONS                                                    │
│                                                                  │
│  [Bulk Price Update]  [Site Configuration]  [View All Shifts]   │
│  [HQ Dashboard]       [EPRA Reports]        [Fleet Accounts]    │
├──────────────────────────────────────────────────────────────────┤
│  NETWORK SNAPSHOT                                                 │
│                                                                  │
│  Sites Active: 4/4   Open Shifts: 3   Disputed: 1 ⚠️            │
│  Total Fuel in Network: 47,230 L  (UX: 18,400 | DX: 26,800)    │
│  Today Revenue: KES 2,470,000 (target: KES 2,800,000)           │
├──────────────────────────────────────────────────────────────────┤
│  PENDING APPROVALS (filtered list views with count badges)       │
│  □ Thika shift SHIFT-2026-00138 — Disputed (wetstock 0.7%)      │
│  □ Mombasa delivery FDD-2026-042 — Variance 0.6% needs approval │
│  □ Westlands price change PLI-2026-019 — Review before next shift│
├──────────────────────────────────────────────────────────────────┤
│  SECTIONS: Configuration | Network Reports | Finance | Compliance│
└──────────────────────────────────────────────────────────────────┘
```

**HQ Menu definition:**

```xml
<menuitem id="menu_fms_hq_root" name="Forecourt HQ" sequence="11"
          groups="fms.group_hq_manager,fms.group_hq_auditor"
          web_icon="fms,static/description/icon_hq.png"/>

<menuitem id="menu_fms_hq_quick" name="Quick Actions" parent="menu_fms_hq_root" sequence="10"/>
<menuitem id="menu_fms_hq_bulk_price" name="Bulk Price Update" parent="menu_fms_hq_quick"
          action="action_fms_bulk_price_update_wizard" sequence="10"/>
<menuitem id="menu_fms_hq_dashboard" name="HQ Dashboard" parent="menu_fms_hq_quick"
          action="action_fms_hq_dashboard" sequence="20"/>

<menuitem id="menu_fms_hq_config" name="Configuration" parent="menu_fms_hq_root" sequence="20"/>
<menuitem id="menu_fms_hq_site_prefs" name="Site Preferences" parent="menu_fms_hq_config"
          action="action_fms_site_preferences" sequence="10"/>
<menuitem id="menu_fms_hq_pump" name="Pumps" parent="menu_fms_hq_config"
          action="action_fms_pump" sequence="20"/>
<menuitem id="menu_fms_hq_calibration" name="Tank Calibration Charts" parent="menu_fms_hq_config"
          action="action_fms_tank_calibration_chart" sequence="30"/>
<menuitem id="menu_fms_hq_pts2_device" name="PTS-2 Devices" parent="menu_fms_hq_config"
          action="action_fms_pts2_device" sequence="40"/>
<menuitem id="menu_fms_hq_pricelist" name="Pump Prices" parent="menu_fms_hq_config"
          action="base.action_product_pricelist_item" sequence="50"/>
<menuitem id="menu_fms_hq_employee" name="Station Staff" parent="menu_fms_hq_config"
          action="hr.open_view_employee_list_my" sequence="60"/>

<menuitem id="menu_fms_hq_reports" name="Network Reports" parent="menu_fms_hq_root" sequence="30"/>
<menuitem id="menu_fms_hq_reports_summary" name="All Sites Shifts" parent="menu_fms_hq_reports"
          action="action_fms_daily_shift_summary" sequence="10"/>
<menuitem id="menu_fms_hq_reports_wetstock" name="Wetstock Trend" parent="menu_fms_hq_reports"
          action="action_fms_wetstock_variance_trend" sequence="20"/>
<menuitem id="menu_fms_hq_reports_cashier" name="Cashier Performance" parent="menu_fms_hq_reports"
          action="action_fms_cashier_performance" sequence="30"/>

<menuitem id="menu_fms_hq_finance" name="Finance" parent="menu_fms_hq_root" sequence="40"/>
<menuitem id="menu_fms_hq_finance_pl" name="Profit and Loss" parent="menu_fms_hq_finance"
          action="account_reports.action_account_report_pl" sequence="10"/>
<menuitem id="menu_fms_hq_finance_gl" name="General Ledger" parent="menu_fms_hq_finance"
          action="account_reports.action_account_report_general_ledger" sequence="20"/>
```

### 29.3 Real-Time Notification Badges

```python
# fms/models/fms_cron_methods.py (called from ir.cron, §10.4)
from odoo import models

class FmsShift(models.Model):
    _inherit = "fms.shift"

    def update_hq_counts(self):
        """Push real-time notification counts to HQ users via bus.bus."""
        disputed = self.search_count([("status", "=", "disputed")])
        pending_deliveries = self.env["fms.fuel.delivery.dip"].search_count(
            [("state", "=", "draft")])
        pending_prices = self.env["product.pricelist.item"].search_count(
            [("fms_effective_shift", "=", "next_shift")])

        self.env["bus.bus"]._sendmany([
            ("fms_hq_counts", "fms_hq_counts", {
                "disputed_shifts": disputed,
                "pending_deliveries": pending_deliveries,
                "pending_prices": pending_prices,
            })
        ])

        # Per-station: alert if shift has been open > configured max hours
        self.env.cr.execute("""
            SELECT id, company_id, opened_at,
                   EXTRACT(EPOCH FROM (NOW() - opened_at)) / 3600 AS hours_open
            FROM fms_shift WHERE status = 'open' AND opened_at IS NOT NULL
            HAVING EXTRACT(EPOCH FROM (NOW() - opened_at)) / 3600 > 26
        """)
        for row in self.env.cr.dictfetchall():
            self.env["bus.bus"]._sendone(
                f"fms_station_{row['company_id']}", "fms_stale_shift_alert",
                {"shift_id": row["id"], "hours": row["hours_open"]})
```

Registered as its own `ir.cron` entry (every minute or two), mirroring ERPNext's `tasks.py` "all" scheduler frequency from §10.4.

---

## 30. Glossary of ERPNext → Odoo Term Mapping

A quick-reference table for anyone moving between the two original ERPNext guides and this Odoo rewrite.

| ERPNext / Frappe Concept | Odoo Equivalent |
|---|---|
| Doctype | Model (`models.Model`) |
| Child Table | `One2many`/`Many2many` field to a child model |
| Single Doctype | A model with a unique constraint (one record per company), or `res.config.settings` |
| `docstatus` (Draft/Submitted/Cancelled) | `state` Selection field with workflow guard logic (no built-in submit/cancel concept) |
| Custom Field (fixtures) | `_inherit` field added on an existing model, shipped in the addon |
| Company | `res.company` (supports `parent_id` for hierarchy) |
| Warehouse | `stock.warehouse` (logistics unit); a physical bin/tank is a `stock.location` |
| Item | `product.template` / `product.product` |
| Moving Average (WAC) | Average Cost (AVCO) costing method |
| Purchase Receipt (GRN) | `stock.picking` (incoming), generated from a `purchase.order` |
| Landed Cost Voucher | `stock.landed.cost` |
| POS Invoice | `pos.order` |
| Sales Invoice | `account.move` (`move_type = 'out_invoice'`), usually originated from a `sale.order` |
| Journal Entry | `account.move` (`move_type = 'entry'`) |
| User Permission | Multi-company `Allowed Companies` on `res.users`, enforced via `ir.rule` |
| Role | Security Group (`res.groups`) |
| Role Permission Manager | `ir.model.access.csv` (model-level) + `ir.rule` (row-level) |
| Workspace | App menu (`ir.ui.menu`) + landing dashboard action |
| Dashboard / Dashboard Chart | Spreadsheet Dashboard app (Enterprise) or custom OWL client action |
| Script Report | SQL-view-backed reporting model (`_auto = False`) or `read_group`/raw-SQL Python method |
| Print Format | QWeb Report (`ir.actions.report`) |
| `hooks.py` (`doc_events`, `scheduler_events`) | Method overrides per model (business logic) + `ir.cron` records (scheduling) |
| `bench` CLI | `odoo-bin` CLI |
| Frappe RQ (background jobs) | `ir.cron` for scheduled jobs; OCA `queue_job` for on-demand async jobs |
| `frappe.publish_realtime()` | `self.env["bus.bus"]._sendone()` / `_sendmany()` |
| `frappe.whitelist(allow_guest=True)` | `@http.route(..., auth="public", csrf=False)` |
| Price List / Item Price | `product.pricelist` / `product.pricelist.item` |
| Territory | `res.country.state`, or a lightweight custom model/tag (`fms.region` in this guide) |
| Employee | `hr.employee` (same concept, same name) |
| Fixtures (`custom_field.json`, `role_permission.json`) | XML/CSV data files shipped in the addon's `data/`/`security/` folders, loaded automatically on install |

---

*End of Document*

**Document Version:** 1.0.0 (Odoo rewrite of ERPNext FMS Guide v3.0.0, Sections 1–30 fully ported)
**Prepared by:** Awo ERP Technical Team
**Status:** Draft — Pending Review and Approval
**Reference Data:** Shell Maanzoni Legacy Screen 18-05-2026; Cash Reconciliation Sheet 17-05-2026
**Companion document:** Odoo PTS-2 Integration Guide v1.0.0
**Next Review:** Q3 2026
