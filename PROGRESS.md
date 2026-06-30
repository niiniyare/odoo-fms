# Odoo FMS Implementation Roadmap
## A Task-by-Task Build Plan — Easiest to Hardest, Each Step Visible and Verifiable

**Companion documents:** `Odoo-FMS-Implementation-Guide.md` (the full spec), `Odoo-PTS2-Integration-Guide.md`, `Odoo-FMS-Developer-Deployment-Maintenance-Guide.md`
**Audience:** Solo developer building incrementally with Claude Code CLI
**Purpose of this document:** Replace "build the whole system" with a sequence of small tasks you can finish in a single sitting, each one ending with something you can click on screen and a checklist that tells you objectively whether it's actually done.

---

## How to Use This Document

Every task below has the same five parts:

- **Depends on** — tasks that must already be ✅ before you start this one. If this is empty, you can start immediately.
- **Goal** — one sentence, what this task adds to the system.
- **Build steps** — the concrete things to do (or ask Claude Code to do), in order.
- **See it working** — the exact click-path in the Odoo UI that proves the feature exists and does something. You should be able to do this in under 2 minutes every time.
- **Definition of Done (metrics)** — objective, checkable conditions. Not "it feels right" — specific numbers, specific test names passing, specific screens showing specific data.

Tasks are grouped into **Milestones**. Each milestone ends with a working, demoable slice of the system — never a half-built model with no UI. Within a milestone, tasks are ordered so each one only needs what came before it.

**Rule of thumb for estimating where you are:** if you cannot currently demo the "See it working" step for the last task you claim to have finished, you are not actually done with it — go back and finish it before starting the next task. This is the single most important discipline in this whole document.

---

## Milestone Map (the big picture)

| Milestone | What you'll be able to demo at the end |
|---|---|
| M0 — Toolchain | Empty `fms` app installed, visible in Odoo's Apps list, no errors |
| M1 — Static Configuration | Companies, products, tanks, pumps, calibration charts all exist and are browsable |
| M2 — Shift Skeleton | You can open and close a bare shift (no readings yet), state machine enforced |
| M3 — Meter Readings | You can record 3-type meter readings per nozzle, validation math runs and shows Pass/Warning/Fail |
| M4 — Dip Readings | You can record tank dips, calibration auto-converts height → volume |
| M5 — Cashiers & Cash | You can open cashier sessions, log cash events, dual-control is enforced |
| M6 — POS/Sales Wiring | Real POS orders link to a shift; attendant is mandatory |
| M7 — Reconciliation | Full shift close produces a per-cashier sheet and wetstock numbers that match the reference dataset |
| M8 — Accounting | Shift close posts a real, balanced journal entry |
| M9 — Deliveries & Drive-Offs | Fuel deliveries and drive-offs are tracked and feed the reconciliation |
| M10 — PTS-2 Integration | A simulated pump transaction lands in Odoo automatically |
| M11 — Reporting & Dashboard | HQ can see cross-station numbers without opening individual shifts |
| M12 — Hardening & Ops | Security tested, backups verified, deployed to a real server |

---

## Milestone 0 — Toolchain & Empty Addon

### Task 0.1 — Local Odoo running with an empty `fms` app installed

**Depends on:** nothing
**Goal:** Prove your dev environment works before writing a single line of business logic.

**Build steps:**
1. Set up Postgres, Odoo core checkout, venv per the Developer Guide §3.
2. Create `addons/fms/__manifest__.py` with just `name`, `version`, `depends: ["stock", "point_of_sale", "account", "hr", "purchase", "sale", "mail"]`, `installable: True`, `application: True`. No `data` list yet.
3. Create an empty `addons/fms/__init__.py`.
4. `make install` (or `odoo-bin -i fms --stop-after-init`).

**See it working:**
Log into Odoo → Apps → remove the "Apps" filter → search "Forecourt" → the FMS app tile appears and shows "Installed."

**Definition of Done:**
- [ ] `make install` exits with code 0 and no traceback in the log
- [ ] FMS app tile visible under Settings → Apps, marked Installed
- [ ] `git log` has one commit: "fms: empty addon skeleton installs cleanly"

---

### Task 0.2 — Root menu and one placeholder screen

**Depends on:** 0.1
**Goal:** Confirm you can add a menu + action + view without touching a real model yet.

**Build steps:**
1. Add `views/fms_menus.xml` with a root menu `Forecourt Station`.
2. Add one menu item pointing at a built-in model you don't own yet, e.g. an `ir.actions.act_window` on `res.company` filtered to nothing useful — purely to prove the wiring works. (You'll replace this in Task 1.1.)
3. Add `views/fms_menus.xml` to the manifest's `data` list.
4. `make upgrade`.

**See it working:**
The "Forecourt Station" app appears in Odoo's main app switcher (top-left), and clicking it opens at least one menu item without an error screen.

**Definition of Done:**
- [ ] App appears in the main navbar app switcher after refresh
- [ ] Clicking the menu item renders a list view with zero errors in the browser console
- [ ] Commit: "fms: root menu wired"

---

## Milestone 1 — Static Configuration (the "master data" you'll reuse for every later task)

These are the easiest real models in the system: no state machine, no cross-model math, just CRUD. They are also blocking dependencies for almost everything else, which is why they come first.

### Task 1.1 — `fms.site.preferences` (one record per company)

**Depends on:** 0.2
**Goal:** Your first real model, with a form, a security row, and a uniqueness constraint — the smallest possible "full vertical slice" (model → security → view → menu).

**Build steps:**
1. Create `models/fms_site_preferences.py` per FMS Guide §6.7 (start with just the threshold fields — skip account-name overrides for now, add them in Task 8.1 when journal posting needs them).
2. `models/__init__.py` → add the import.
3. `security/ir.model.access.csv` → one row granting the base `base.group_user` read/write for now (you'll tighten this in Milestone 12).
4. `views/fms_site_preferences_views.xml` → a form view + list view + action.
5. Add a menu item under the root menu.
6. Update manifest `data` order: access csv → views → menus.
7. `make upgrade`.

**See it working:**
Forecourt Station → Configuration → Site Preferences → New → fill in a company and the default threshold values → Save → record persists, reopening shows the same values.

**Definition of Done:**
- [ ] Can create, edit, save, and reopen a `fms.site.preferences` record through the UI
- [ ] Creating a second record for the *same* company raises a clear validation error (uniqueness constraint working)
- [ ] `make test` still passes (no test yet, but the suite must still run clean)
- [ ] Commit: "fms: site preferences model"

---

### Task 1.2 — Fuel products (`product.template` extension)

**Depends on:** 1.1 (reuses the same manifest/security/view wiring pattern)
**Goal:** The three fuel grades exist as real Odoo products with the FMS-specific fields, ready to be sold/stocked later.

**Build steps:**
1. `models/product_template.py` → `_inherit = "product.template"` adding `fms_is_fuel_product`, `fms_fuel_grade` per FMS Guide §6.3.
2. Add a small `<field>` to the existing product form view (inherited view, not a new screen) so the two new fields show up on the standard Odoo product page.
3. Seed data: create `FUEL-PMS-UNL`, `FUEL-PMS-VP`, `FUEL-AGO` as storable products with AVCO costing, using either the UI or a `data/product_data.xml` seed file (prefer the seed file — it's reproducible on every fresh DB).

**See it working:**
Inventory app → Products → the three fuel products exist, each showing "Is Fuel Product" checked and the correct grade selected, each Litre-UoM, Average Cost.

**Definition of Done:**
- [ ] All three products exist after a fresh `make install` (i.e., they come from seed data, not manual clicking)
- [ ] Each has `fms_is_fuel_product = True` and the correct `fms_fuel_grade`
- [ ] Costing method is Average Cost (AVCO) on all three
- [ ] Commit: "fms: fuel products + grade field"

---

### Task 1.3 — Tank locations (`stock.location` extension)

**Depends on:** 1.2 (tanks reference a fuel product)
**Goal:** Tank 1/2/3 exist as real stock locations you can see fuel quantities in.

**Build steps:**
1. `models/stock_location.py` → `_inherit` adding `fms_is_fuel_tank`, `fms_capacity_litres`, `fms_pts2_tank_number`, `fms_fuel_product_id` per FMS Guide §6.4.
2. Inherited view: small addition to the stock location form.
3. Seed data: Tank 1 (V-Power), Tank 2 (Unleaded), Tank 3 (Diesel), nested under the station's warehouse stock location, each linked to its product.

**See it working:**
Inventory → Configuration → Locations → the three tanks exist under the warehouse, each showing Capacity and linked Fuel Product. Inventory → Reporting → Valuation shows 0 litres in each (expected — no stock moves yet).

**Definition of Done:**
- [ ] Three tank locations exist after fresh install, correctly nested and linked
- [ ] `fms_capacity_litres` is set on all three (use real Shell Maanzoni figures if known, otherwise a placeholder you'll correct later)
- [ ] Commit: "fms: tank locations"

---

### Task 1.4 — `fms.pump` and `fms.pump.nozzle`

**Depends on:** 1.3 (a nozzle references a tank)
**Goal:** The 8 physical pumps/nozzles at Shell Maanzoni exist as data, organized by island.

**Build steps:**
1. `models/fms_pump.py` — fields: `name`, `island_id` or simple `island` Char/Selection for now, `is_active`.
2. `models/fms_pump_nozzle.py` — fields: `pump_id`, `nozzle_number`, `tank_location_id`, `is_active`.
3. List+form views, menu under Configuration.
4. Seed data (or manual entry) for the 8 real pumps (U5, U6, L5, L6, U7, U8, L7, L8) from the reference dataset, each nozzle pointing at the correct tank.

**See it working:**
Configuration → Pumps → 8 pumps listed, each expandable to show its nozzle(s) and which tank it draws from.

**Definition of Done:**
- [ ] 8 pumps + their nozzles exist, matching the reference table in FMS Guide §1.3
- [ ] Each nozzle correctly points at Tank 1, 2, or 3 per its fuel grade (UX/VP→ correct tanks, DX → diesel tank)
- [ ] Commit: "fms: pumps and nozzles"

---

### Task 1.5 — `fms.tank.calibration.chart` (header + lines)

**Depends on:** 1.3
**Goal:** A tank's dip-height-to-volume strapping table exists and the interpolation function returns correct numbers — this is your first **pure logic** task (no state machine, just math), good practice before the harder formulas later.

**Build steps:**
1. `models/fms_tank_calibration_chart.py` (header: tank, capacity, certifier, cert number, calibration date) + `fms_tank_calibration_chart_line.py` (child: `dip_height_mm`, `volume_ltrs`).
2. Implement `derive_volume_from_dip()` per FMS Guide §7.7.
3. Editable list view for the chart lines, embedded in the header form.
4. **Write the unit test now** (FMS Guide §20.3 pattern) — this is cheap because the function is pure, and it's the first test in your suite.

**See it working:**
Configuration → Tank Calibration Charts → New → Tank 2 → add a few rows (e.g. 0mm→0L, 1000mm→10000L, 2000mm→25000L) → Save. Then in the Odoo shell: `env["fms.tank.calibration.chart"].browse(<id>).derive_volume_from_dip(500)` returns `5000.0`.

**Definition of Done:**
- [ ] `make test` shows a passing `TestCalibration` (or similarly named) test class with at least 3 cases: exact boundary, midpoint interpolation, out-of-range raises
- [ ] Chart for at least one real Shell Maanzoni tank entered through the UI
- [ ] Commit: "fms: tank calibration chart + interpolation (tested)"

> **Milestone 1 demo checkpoint:** at this point you should be able to walk someone through Odoo and show: companies → fuel products → tanks with capacities → pumps/nozzles per island → a calibration chart that correctly converts a dip reading to a volume. Nothing transactional yet — that's fine, this is your foundation.

---

## Milestone 2 — Shift Skeleton (state machine only, no readings yet)

### Task 2.1 — `fms.shift` with fields but no state machine yet

**Depends on:** Milestone 1 (references company/station)
**Goal:** A shift record exists and can be created/listed — deliberately *before* adding the state machine, so you can verify basic CRUD first and add complexity in the next task.

**Build steps:**
1. `models/fms_shift.py` with all fields from FMS Guide §7.3 **except** the `write()` override and `ALLOWED_TRANSITIONS` — `status` is just a plain Selection field for now, no guard logic.
2. `ir.sequence` for shift numbering (`data/ir_sequence_data.xml`).
3. Form + list view with a `statusbar` widget on `status` (it'll look like a real workflow even before the guard logic exists).
4. Menu under "Shift Operations."

**See it working:**
Shift Operations → Shifts → New → fill date/label/cashier/supervisor → Save → status shows "Draft" in the status bar, you can manually click through to "Open," "Closed," etc. with no enforcement (yet).

**Definition of Done:**
- [ ] Can create a shift, see it in the list, reopen it, see all fields persist
- [ ] Shift name auto-generates from the sequence (e.g. `SHIFT-2026-00001`)
- [ ] Commit: "fms: shift model (no state machine yet)"

---

### Task 2.2 — Shift state machine + single-open-shift-per-station constraint

**Depends on:** 2.1
**Goal:** The exact rules from FMS Guide §2 Rule 1 and §7.3 are enforced — this is your first real business-logic task with a clear pass/fail test.

**Build steps:**
1. Add `ALLOWED_TRANSITIONS` dict and the `write()` override per FMS Guide §7.3.
2. Add `@api.constrains` for `cashier_id != supervisor_id` and the single-open-shift-per-station rule.
3. Write tests: invalid transition raises, valid transition succeeds, two open shifts at the same station raises, same cashier/supervisor raises.

**See it working:**
Try to manually edit a shift's status field to skip from "Draft" straight to "Closed" — Odoo shows a validation error with the exact allowed-transitions message. Try opening a second shift at a station that already has one open — same kind of error.

**Definition of Done:**
- [ ] `make test` passes a `TestFmsShift` class covering: valid transition, invalid transition (rejected), duplicate open shift (rejected), same cashier/supervisor (rejected)
- [ ] Manually reproducing each rejection in the UI shows a human-readable error, not a raw traceback
- [ ] Commit: "fms: shift state machine + invariants (tested)"

> **Milestone 2 demo checkpoint:** you can open a shift, watch the status bar enforce the legal transition order, and prove (via test + manual UI attempt) that the system refuses to skip steps or double-open a station.

---

## Milestone 3 — Meter Readings (the core domain logic of the whole system)

This is the heart of FMS. Breaking it into sub-tasks matters a lot here — don't try to build the whole meter-reading + validation engine in one sitting.

### Task 3.1 — `fms.meter.reading` CRUD only (no validation logic yet)

**Depends on:** 1.4 (pumps/nozzles), 2.1 (shift exists)
**Goal:** You can record a single reading and see it listed against a shift — prove the model+view wiring before adding any math.

**Build steps:**
1. `models/fms_meter_reading.py` with all fields from FMS Guide §7.4, but skip the `@api.constrains` validations and the immutability `write()` override for now.
2. Embed an editable list of `meter_reading_ids` inside the shift form (a new notebook page, "Meter Readings").
3. List+form view.

**See it working:**
Open a shift → Meter Readings tab → New → pick a pump, nozzle 2, meter type Electronic Volume, reading position Shift Open, totalizer value 171275183.070 → Save → row appears in the embedded list.

**Definition of Done:**
- [ ] Can add multiple readings (different meter types, different nozzles) to one shift and see them all listed
- [ ] Commit: "fms: meter reading CRUD"

---

### Task 3.2 — Meter reading validation constraints (closing ≥ opening, positive value, immutability)

**Depends on:** 3.1
**Goal:** The data-integrity rules from FMS Guide §7.4 are enforced — these are simple, independent constraints, good as a standalone task before the harder Check A/B math.

**Build steps:**
1. Add `@api.constrains` for positive totalizer value.
2. Add `@api.constrains` for "closing must have a matching opening reading, and closing ≥ opening."
3. Add the `write()` override blocking edits to a `confirmed` reading (immutability), with the amendment-reason requirement.
4. `action_confirm()` method + a confirm button on the form.
5. Tests: zero/negative value rejected, closing without opening rejected, closing < opening rejected, editing a confirmed reading rejected, amendment without reason rejected.

**See it working:**
Try entering a closing reading with a value lower than the matching opening reading — clear validation error. Confirm a reading, then try to edit its totalizer value — blocked with a message pointing you to create an Amendment instead.

**Definition of Done:**
- [ ] All 5 test cases above pass in `make test`
- [ ] Each rejection reproduced manually in the UI shows the correct human-readable message
- [ ] Commit: "fms: meter reading constraints + immutability (tested)"

---

### Task 3.3 — `fms.meter.validation.result` + Check A / Check B engine

**Depends on:** 3.2
**Goal:** Port the exact formulas and thresholds from FMS Guide §4.2–4.3 and §20.1, and prove they reproduce the real Shell Maanzoni numbers.

**Build steps:**
1. `models/fms_meter_validation_result.py` (readonly, computed-only model).
2. Implement `_validate_nozzle()` and `_lock_pump()` exactly per FMS Guide §7.5.
3. **Port every test case from FMS Guide §20.1 verbatim** — these use real station data (U7 0.65%→Fail, L5 0.48%→Warning, U8 0.19%→Pass, the critical-lock case) — they are your acceptance criteria, not just "nice to have" tests.
4. Add a button on the shift form, "Run Meter Validation," that loops over all confirmed closing readings for the shift and creates the result rows.
5. List view of results embedded as a new shift notebook tab, with status (Pass/Warning/Fail/Critical) shown as colored badges (use a `widget="badge"` with `decoration-*` attributes — purely cosmetic, skip if short on time).

**See it working:**
On a shift with full opening+closing readings entered for a few nozzles (use the real U7/U8/L5/L8 figures from FMS Guide §1.3), click "Run Meter Validation" → a result row appears per nozzle with the correct Pass/Warning/Fail and the correct discrepancy numbers, matching the guide's worked examples to the cent/percent.

**Definition of Done:**
- [ ] All 7 test cases from FMS Guide §20.1 pass, including the critical-lock-pump case (`fms.pump.is_active` flips to False)
- [ ] Manually running validation against the real U7/L5/U8/L8 readings in the UI reproduces the exact Pass/Warning/Fail verdicts from the guide's table
- [ ] Commit: "fms: meter validation engine (Check A + Check B, fully tested against reference data)"

> **Milestone 3 demo checkpoint:** this is your first genuinely impressive demo. Walk through: open a shift → enter three-type opening readings for a few nozzles → enter closing readings, including one engineered to fail Check B → click "Run Meter Validation" → see the Fail row, see the pump auto-locked. This single checkpoint proves the most commercially valuable piece of the whole system works.

---

## Milestone 4 — Dip Readings

### Task 4.1 — `fms.tank.dip.reading` CRUD + capacity/water constraints

**Depends on:** 1.5 (calibration chart), 2.1 (shift exists)
**Goal:** Record a dip reading and have it auto-derive volume from the calibration chart — reuses the pure function from Task 1.5 inside a transactional context.

**Build steps:**
1. `models/fms_tank_dip_reading.py` per FMS Guide §7.6.
2. Wire `volume_observed_l` to auto-compute from `dip_height_mm` + the tank's calibration chart (an `@api.onchange` for live UI feedback **plus** a server-side default-on-create so the value is correct even via API/import — remember the onchange-isn't-real-validation lesson from the Developer Guide §5.3).
3. `@api.constrains` for capacity exceeded and the >20mm water-level message-post.
4. Embed in shift form as a new notebook tab.

**See it working:**
Shift → Dip Readings tab → New → Tank 2 → enter a dip height that exists in your calibration chart's range → `volume_observed_l` auto-fills correctly without you typing it. Enter water_level_mm = 25 → save → a chatter message appears flagging the >20mm threshold.

**Definition of Done:**
- [ ] Volume auto-derivation matches the calibration chart's interpolation exactly (cross-check against the Task 1.5 shell test)
- [ ] Capacity-exceeded and water-level-alert behaviors both demonstrated in the UI
- [ ] Commit: "fms: tank dip readings with calibration auto-derive"

> **Milestone 4 demo checkpoint:** open a shift, record opening and closing dips for all three tanks, watch volumes auto-calculate from heights.

---

## Milestone 5 — Cashiers & Cash Events

### Task 5.1 — `fms.cashier.session` CRUD

**Depends on:** 2.1
**Goal:** Multiple cashier sessions per shift exist, matching the "4–5 cashiers per shift" pattern from the reference dataset.

**Build steps:**
1. `models/fms_cashier_session.py` per FMS Guide §7.8 (skip `pos_session_id` linkage for now — that comes in Milestone 6).
2. Embed in shift form as a notebook tab, editable list.

**See it working:**
Open a shift → Cashier Sessions → add Swedi Abuti, Peter Mbeve, Joseph Matale, Joel Musembi, and the supervisor float row — five rows, matching the reference cash-reconciliation sheet's cashier list.

**Definition of Done:**
- [ ] Can add/list 5 cashier sessions on one shift
- [ ] Commit: "fms: cashier sessions"

---

### Task 5.2 — `fms.cash.event` with dual-control enforcement

**Depends on:** 5.1
**Goal:** Float/pickup/payout/safe-drop events exist and Rule 7 (dual control) is mechanically enforced, not just policy.

**Build steps:**
1. `models/fms_cash_event.py` per FMS Guide §7.9.
2. `@api.constrains` for `authorised_by_id != cashier_session.cashier_id`.
3. `@api.constrains` for reference-number-required on pickup/safe-drop.
4. Tests for both constraints.

**See it working:**
Try to log a Cash Pickup where the authoriser is the same person as the cashier — rejected. Try to log a Safe Drop with no envelope reference — rejected. Do it correctly with two different people and a reference — succeeds.

**Definition of Done:**
- [ ] Both constraint tests pass
- [ ] Manual reproduction of both rejections in the UI
- [ ] Commit: "fms: cash events with dual control (tested)"

> **Milestone 5 demo checkpoint:** open a shift, add cashier sessions, log a float issue and a cash pickup with proper dual control, demonstrate the system refusing a single-person pickup attempt.

---

## Milestone 6 — POS / Sales Wiring (touches existing Odoo models — be careful)

### Task 6.1 — `pos.order` extension: shift auto-link + mandatory attendant

**Depends on:** 2.2 (shift open/closed states), Milestone 1 (fuel products must exist and be sellable)
**Goal:** A real Odoo POS order, sold through the standard POS app, automatically links to the open shift and cannot be paid without an attendant — this is your first task that modifies *existing* Odoo behavior, so go slowly and test the standard POS flow isn't broken.

**Build steps:**
1. `models/pos_order.py` per FMS Guide §8.1 — add the fields, the `create()` auto-link, and the `action_pos_order_paid()` guard.
2. Configure a POS Configuration for the station if you haven't already (standard Odoo POS setup, not FMS-specific).
3. **Before** changing anything, do one full manual POS sale (open session → sell a fuel product → pay → close session) to confirm vanilla POS works in your dev environment.
4. Apply the `_inherit`, `make upgrade`, then repeat the same manual POS sale and confirm it still works *and* now requires an attendant.

**See it working:**
Open the POS app, start a session, add a fuel product to an order, attempt to pay without setting an attendant — blocked. Set the attendant, pay — succeeds. Open the underlying shift record — the `pos.order` is now visible/linked (via a smart button or the one2many you choose to expose).

**Definition of Done:**
- [ ] Vanilla POS checkout still works end-to-end (you didn't break core POS)
- [ ] Paying without an attendant is blocked with a clear message
- [ ] A paid order is provably linked to the currently open shift (check via the shell: `order.fms_shift_id == open_shift`)
- [ ] Commit: "fms: pos.order shift link + mandatory attendant"

---

### Task 6.2 — `account.move` extension (fleet/credit invoices)

**Depends on:** 6.1
**Goal:** Customer invoices for fleet/credit sales also link to a shift, feeding the "Invoices" column of the reconciliation sheet later.

**Build steps:**
1. `models/account_move.py` per FMS Guide §8.2 — same field pattern as 6.1, applied to `out_invoice` moves instead.
2. Small view inheritance to surface the fields on the invoice form.

**See it working:**
Create a customer invoice for a fleet customer, set the FMS fields, confirm it — visible and linked to the shift the same way POS orders are.

**Definition of Done:**
- [ ] Can create and post a fleet invoice with `fms_shift_id` set
- [ ] Commit: "fms: account.move shift link"

> **Milestone 6 demo checkpoint:** sell fuel through real Odoo POS, with attendant enforcement, linked to a shift. Issue one credit invoice the same way. This is the moment FMS stops being "data entry forms" and starts touching real Odoo transactions.

---

## Milestone 7 — Reconciliation (the payoff milestone — reproduce the reference numbers exactly)

This is intentionally the most complex milestone. Don't attempt it as one task — the three sub-tasks below isolate cash math, wetstock math, and the orchestration button from each other.

### Task 7.1 — Cashier reconciliation line computation (cash formula only)

**Depends on:** 5.2, 6.1
**Goal:** Reproduce the exact verified formula from FMS Guide §7.10 against the real 17-05-2026 dataset.

**Build steps:**
1. `models/fms_shift_reconciliation.py` (header) + `fms_shift_reconciliation_cashier_line.py` (child) per FMS Guide §7.10.
2. Write the per-cashier computation method (pulls `sales`/`invoices`/`pos_payments`/`visa_card` from linked `pos.order`/`account.move` records, `receipts`/`payments_out` from `fms.cash.event`, computes `expected_cash` and `cash_over_under`).
3. **Before writing UI**, write this as a pure-ish method you can call from the shell, and test it against the three worked examples in FMS Guide §7.10 (Swedi Abuti → 14,300.70; Peter Mbeve → 13,183.50; Joseph Matale → 1,649.23).

**See it working:**
In the Odoo shell, build (or load via a fixture) the 17-05-2026 dataset for one shift, call the computation, and print the resulting `expected_cash` per cashier — they must match the guide's numbers to the cent.

**Definition of Done:**
- [ ] A test reproduces all three worked examples from FMS Guide §7.10 to the cent
- [ ] Commit: "fms: cashier reconciliation cash formula (tested against reference dataset)"

---

### Task 7.2 — Tank wetstock line computation

**Depends on:** 4.1, 3.3 (needs both dip readings and meter-validation elec/mech sold volumes)
**Goal:** Reproduce FMS Guide §13.1's `compute_tank_wetstock` exactly, including classification thresholds.

**Build steps:**
1. `fms_shift_reconciliation_tank_line.py` child model.
2. Implement `compute_tank_wetstock()` exactly per FMS Guide §13.1.
3. **Port every test case from FMS Guide §20.2 verbatim** — balanced shift, critical loss, delivery included, the Maanzoni UX/DX reference cases.

**See it working:**
Shell-test the function against the Tank 2 UX reference numbers (opening 7000L, 955.99L sold, closing dip 6040L → Normal classification, ~4L variance) — matches exactly.

**Definition of Done:**
- [ ] All 5 test cases from FMS Guide §20.2 pass
- [ ] Commit: "fms: wetstock computation (tested against reference dataset)"

---

### Task 7.3 — "Compute Reconciliation" orchestration + Close Shift wizard

**Depends on:** 7.1, 7.2, 3.3
**Goal:** One button that runs meter validation, computes both reconciliation line types, and creates/updates the `fms.shift.reconciliation` header — the first task where multiple subsystems you built separately are wired together into the actual user workflow from FMS Guide §11.3.

**Build steps:**
1. `wizards/fms_close_shift_wizard.py` — a `TransientModel` with buttons "Run Meter Validation" (calls Task 3.3's logic) and "Compute Reconciliation" (calls 7.1 + 7.2's logic, idempotently — running it twice should produce the same result, not duplicate rows).
2. Wizard form view, opened from a button on the shift form when `status == "closing"`.
3. End-to-end manual test: build the full 17-05-2026 reference shift (all cashiers, all nozzles, all tanks) and run the wizard.

**See it working:**
Open a shift in `closing` status with the full reference dataset entered → click the Close Shift wizard button → Run Meter Validation → Compute Reconciliation → the resulting cashier lines and tank lines exactly match the FMS Guide §1.3 reference tables (cashier totals: 621,591.43 sales, (983.43) total over/under; per-cashier breakdown matching the table row by row).

**Definition of Done:**
- [ ] Running the wizard twice on the same shift doesn't create duplicate reconciliation lines (idempotent recompute)
- [ ] The full reference dataset, entered once, reproduces every number in the FMS Guide §1.3 cash reconciliation table
- [ ] Commit: "fms: close shift wizard orchestrating validation + reconciliation"

> **Milestone 7 demo checkpoint:** this is the headline demo of the entire project. Walk through an entire shift lifecycle — open, enter readings/dips/cash events/POS sales for the full reference dataset, close — and show the system reproducing, unprompted, the exact same numbers as the paper reconciliation sheet this project exists to replace.

---

## Milestone 8 — Accounting

### Task 8.1 — Account-name resolution + `fms.site.preferences` account fields

**Depends on:** 1.1, Milestone 1 chart of accounts set up in Odoo
**Goal:** Centralize account lookups before writing the posting logic that depends on them.

**Build steps:**
1. Add the account-override fields to `fms.site.preferences` (FMS Guide §6.7's bottom rows).
2. `models/fms_account_helper.py` per FMS Guide §10.1 — `get_account()` and `get_fuel_accounts()`.
3. Set up the actual Chart of Accounts entries (Till — Active, Safe — Main, Cash Short/Over, etc.) per FMS Guide §6.2, either manually or via seed data.

**See it working:**
In the shell: `env["fms.account.helper"].get_account("till_active", company)` returns the correct `account.account` record.

**Definition of Done:**
- [ ] All account short-names from FMS Guide §10.1's `_DEFAULT_FIELD_MAP` resolve correctly for the test company
- [ ] Commit: "fms: account resolution helper"

---

### Task 8.2 — Journal entry posting (the highest-stakes task in the project)

**Depends on:** 7.3, 8.1
**Goal:** Reproduce the exact journal entry template from FMS Guide §11.4, balanced to the cent, posted as a real confirmed `account.move`.

**Build steps:**
1. Implement `post_shift_journal_entry()` exactly per FMS Guide §11.4, including the balance-check guard (`abs(total_dr - total_cr) > 0.05` raises).
2. Wire it to an "Approve & Post" button on the reconciliation record, only enabled once reconciliation is computed and (if `requires_approval`) an approver is set.
3. Write a test that builds the reference shift, runs the full Milestone 7 pipeline, posts the journal entry, and asserts: the move is posted (`state == "posted"`), total debit == total credit, and the specific line amounts match FMS Guide §11.4's worked example (Till debits per cashier, Cash Short/Over lines, etc.)

**See it working:**
On the fully-reconciled reference shift, click "Approve & Post" → a posted `account.move` is created → opening it in Accounting shows the exact line-by-line breakdown from FMS Guide §11.4 → the shift's status can now move to `closed`.

**Definition of Done:**
- [ ] The posting test passes, matching every line amount in the FMS Guide §11.4 worked example
- [ ] Attempting to post an unbalanced entry (engineer a broken test case) is rejected by the guard before reaching Odoo's own posting validation
- [ ] Shift cannot reach `closed` status without `journal_entry_id` set (re-confirm Task 2.2's guard still holds)
- [ ] Commit: "fms: journal entry posting (tested, balanced)"

> **Milestone 8 demo checkpoint:** close the reference shift all the way to `closed`, open the posted journal entry in Odoo's standard Accounting UI, and show a real accountant-readable, balanced entry that matches the paper trail.

---

## Milestone 9 — Deliveries & Drive-Offs

### Task 9.1 — `fms.fuel.delivery.dip` + `stock.picking` extension

**Depends on:** 4.1 (dip readings), Milestone 1 (products/tanks)
**Goal:** Reproduce the delivery variance formula from FMS Guide §12.1 and gate picking validation on the dip-measured (not docket) quantity.

**Build steps:**
1. `models/fms_fuel_delivery_dip.py` + `models/stock_picking.py` extension per FMS Guide §7.11 and §8.3.
2. Compute `fms_received_qty_l` / `fms_delivery_variance_l`.
3. Test: the ≤0.5% auto-accept vs >0.5% dispute threshold from FMS Guide §12.2.

**See it working:**
Create a delivery dip with before/after dips and a docket volume engineered to be within tolerance → status auto-suggests "Accept." Engineer one outside tolerance → suggests "Dispute," and the linked picking cannot be validated at the docket quantity.

**Definition of Done:**
- [ ] Variance threshold test passes both branches
- [ ] Commit: "fms: fuel delivery dip + variance threshold (tested)"

---

### Task 9.2 — `fms.drive.off.record`

**Depends on:** 2.1, 8.1
**Goal:** Drive-off losses are tracked and post their own small journal entry on confirm.

**Build steps:**
1. `models/fms_drive_off_record.py` per FMS Guide §7.11 — manager-authorisation requirement, police-reference-required-if-≥KES-500 constraint, posts `DR Drive-Off Losses / CR Fuel Sales` on confirm.
2. Tests for both constraints and the posting.

**See it working:**
Log a drive-off of KES 600 with no police reference — blocked. Add the reference, confirm — a small balanced journal entry appears.

**Definition of Done:**
- [ ] Both constraint tests pass
- [ ] Posted entry is balanced
- [ ] Commit: "fms: drive-off records (tested)"

> **Milestone 9 demo checkpoint:** record one delivery (one accepted, one disputed scenario) and one drive-off, show both feeding into the wetstock/financial picture from Milestones 7–8.

---

## Milestone 10 — PTS-2 Integration

Don't start this until Milestones 1–9 work entirely on manual data entry — PTS-2 is just an automated way of creating the same records you've already proven work correctly by hand.

### Task 10.1 — `fms.pts2.device` + `fms.pump.configuration` (static mapping, no network yet)

**Depends on:** 1.4
**Goal:** The hardware-to-Odoo mapping models exist, independent of any actual PTS-2 traffic.

**Build steps:**
1. `models/fms_pts2_device.py`, `models/fms_pump_configuration.py` per FMS Guide §7.11.
2. Simple list/form views.

**See it working:**
Configuration → PTS-2 Devices → create one record with a placeholder `device_id` → link Pump Configurations mapping each `fms.pump` to a `pts_pump_id`.

**Definition of Done:**
- [ ] One device + 8 pump-configuration mappings exist (matching the 8 pumps from Task 1.4)
- [ ] Commit: "fms: pts2 device + pump configuration mapping"

---

### Task 10.2 — `fms.forecourt.transaction` + HTTP receiver controller

**Depends on:** 10.1, 3.1 (eventually feeds meter context, but the controller itself just needs the staging model)
**Goal:** Reproduce FMS Guide §10.2's controller, provable with a plain `curl`/Postman request before any real PTS-2 hardware is involved.

**Build steps:**
1. `models/fms_forecourt_transaction.py` with the `_sql_constraints` dedup key.
2. `controllers/pts2.py` per FMS Guide §10.2, HMAC-verified.
3. Manually craft a fake `PumpTransaction` JSON payload (copy FMS/PTS-2 Guide §4.6's example), sign it with the test secret, and `curl` it at your local Odoo instance.

**See it working:**
```bash
curl -X POST http://localhost:8069/fms/pts2/receive \
  -H "Content-Type: application/json" \
  -H "X-Signature: <computed-hmac>" \
  -d @sample_pump_transaction.json
```
returns `{"status": "ok"}`, and an `fms.forecourt.transaction` record now exists in Odoo with the matching data. Send the *exact same* payload again — still `{"status": "ok"}`, but no duplicate record created.

**Definition of Done:**
- [ ] Test (using Odoo's HTTP test client, not a real `curl`, for CI-friendliness) covers: valid signature creates a record, invalid signature returns 401, duplicate `TransactionNumber`+`DeviceId` is silently deduplicated
- [ ] Manual `curl` reproduction works against your local dev server
- [ ] Commit: "fms: pts2 receiver controller (tested, dedup verified)"

---

### Task 10.3 — Outbound commands (price push, pump authorise) — optional, only if hardware/SDK is available

**Depends on:** 10.2
**Goal:** Odoo can call the PTS-2's Web Server API per the Developer/PTS-2 Guide §10.5 Pattern A.

**Build steps:**
1. `models/fms_pts2_commands.py` per FMS Guide §10.5.
2. If you have the SDK simulator (`SimUniPump.exe` / `PTS2-SDK-001`), test against it; otherwise, mock the `requests` call in a unit test and defer real-hardware verification to a deployment checklist item.

**See it working:**
Against the SDK simulator: trigger a price push from Odoo, observe the simulator's display update.

**Definition of Done:**
- [ ] Unit test mocking the HTTP call passes
- [ ] (If hardware available) manual verification against the simulator documented in `docs/decisions.md`
- [ ] Commit: "fms: pts2 outbound commands"

> **Milestone 10 demo checkpoint:** send a simulated pump transaction via `curl`/Postman and watch it appear as a new `fms.forecourt.transaction` in Odoo within seconds, with duplicates correctly ignored.

---

## Milestone 11 — Reporting & Dashboard

Everything here is read-only over data that already exists — by far the lowest-risk milestone, deliberately last.

### Task 11.1 — Daily Shift Summary report

**Depends on:** Milestone 7
**Goal:** One SQL-view-backed model reproducing FMS Guide §27.2.1.

**Build steps:** as described in the FMS Implementation Guide §27.2.1 — `_auto = False` model + `init()` SQL view.

**See it working:** a filterable, exportable list view showing one row per shift with revenue/variance columns.

**Definition of Done:**
- [ ] Report shows correct totals for the reference shift, cross-checked against Milestone 7/8's numbers
- [ ] Commit: "fms: daily shift summary report"

---

### Task 11.2 — Wetstock variance trend + meter discrepancy log reports

**Depends on:** 11.1 (same pattern, copy it)
**Goal:** Two more SQL-view-backed reports, per FMS Guide §27.2.3 and §27.2.4.

**Definition of Done:**
- [ ] Both reports return correct rows filtered by date range and company
- [ ] Commit: "fms: wetstock trend + meter discrepancy reports"

---

### Task 11.3 — HQ Dashboard data methods + minimal OWL widget (or Spreadsheet Dashboard if Enterprise)

**Depends on:** 11.1, 11.2
**Goal:** One screen an HQ user can open without drilling into individual shifts.

**Build steps:** `models/fms_dashboard.py` methods per FMS Guide §28.2, plus either the OWL client action (§28.3) or, if you have Odoo Enterprise, pivot/graph views pinned to a Spreadsheet Dashboard instead (less code, prefer this if available).

**Definition of Done:**
- [ ] Dashboard loads and shows real numbers for at least: open shifts, today's revenue by site, wetstock alerts
- [ ] Commit: "fms: HQ dashboard"

> **Milestone 11 demo checkpoint:** open the HQ Dashboard and see real, correct, cross-station numbers without touching a single shift record directly.

---

## Milestone 12 — Hardening & Operations

### Task 12.1 — Real security groups + record rules (replace the temporary "everyone can do everything" from Task 1.1)

**Depends on:** every model task above (touches all of them)
**Goal:** Reproduce FMS Guide §6.5–6.6, §16's permission matrix, and prove it with negative tests.

**Build steps:**
1. Create all six security groups per FMS Guide §6.5.
2. Rewrite `ir.model.access.csv` with the real per-group rows for every model (no more blanket `base.group_user` access).
3. Add the company `ir.rule` to every FMS model with a `company_id`.
4. **Write negative tests**: a cashier-group user cannot read another company's shift; a cashier cannot write to `fms.shift.reconciliation`; an HQ Auditor can read but not write anything.

**See it working:**
Log in as a test user assigned only the Site Cashier group, restricted to Company A — attempting to open a Company B shift via direct URL/ID shows an access error, not the record.

**Definition of Done:**
- [ ] At least one negative-permission test per major model passes
- [ ] Manual cross-company access attempt blocked in the UI
- [ ] Commit: "fms: full security groups + record rules (tested)"

---

### Task 12.2 — Backup/restore drill

**Depends on:** nothing technical, but should happen before real data enters the system
**Goal:** Prove you can actually recover from a backup, not just that the backup script runs.

**Build steps:** per Developer Guide §15 — script the backup, then **actually restore it** to a `_restore_test` database and verify a few known records are present.

**Definition of Done:**
- [ ] A restore-test database, built purely from a backup, shows the correct row counts for `fms.shift`/`fms.shift.reconciliation`
- [ ] Documented in `docs/decisions.md` or a `RUNBOOK.md`: exact restore command sequence
- [ ] Commit: "ops: backup/restore drill documented and verified"

---

### Task 12.3 — Production deployment

**Depends on:** 12.1, 12.2, and ideally Milestones 1–9 fully demoed against a clean dataset
**Goal:** The system is reachable at a real domain, behind TLS, running under systemd (or Docker), per Developer Guide §13.

**Definition of Done:**
- [ ] Production checklist from Developer Guide §13.5 fully checked off
- [ ] A real (or realistic test) shift can be opened/closed/reconciled/posted against the production database
- [ ] First production backup taken and verified before any real operational data enters the system
- [ ] Commit/tag: `v1.0.0` — "fms: first production deployment"

---

### Task 12.4 — Parallel-run validation (the real-world acceptance test)

**Depends on:** 12.3
**Goal:** Per FMS Guide §19's migration plan — run FMS alongside the paper/legacy process for 2 weeks and prove agreement.

**Definition of Done:**
- [ ] For at least 10 shifts, FMS's computed cash over/under matches the paper sheet's figure within a documented tolerance (ideally exact, to the cent)
- [ ] For at least 10 shifts, FMS's wetstock variance classification matches what a manual check would conclude
- [ ] Sign-off recorded (even just a dated note in `docs/decisions.md`) before cutting over fully

---

## Quick-Reference: Dependency Graph

```
0.1 → 0.2
0.2 → 1.1 → 1.2 → 1.3 → 1.4
                 1.3 → 1.5
1.1 + 1.4 → 2.1 → 2.2
1.4 + 2.1 → 3.1 → 3.2 → 3.3
1.5 + 2.1 → 4.1
2.1 → 5.1 → 5.2
2.2 + 1.x → 6.1 → 6.2
5.2 + 6.1 → 7.1
4.1 + 3.3 → 7.2
7.1 + 7.2 + 3.3 → 7.3
1.1 + 1.x(accounts) → 8.1
7.3 + 8.1 → 8.2
4.1 + 1.x → 9.1
2.1 + 8.1 → 9.2
1.4 → 10.1 → 10.2 → 10.3
7.x → 11.1 → 11.2 → 11.3
(all) → 12.1
(any time) → 12.2
12.1 + 12.2 → 12.3 → 12.4
```

Print or pin this table somewhere visible — it answers "what can I work on next" at a glance whenever you finish a task, and it's the single artifact worth handing to Claude Code at the start of a session if you want it to suggest "what's next" correctly (it can read this file directly).

---

## Tracking Progress

Keep a `PROGRESS.md` at the repo root, one line per task, updated the moment a task's "Definition of Done" is fully checked — not before:

```markdown
# FMS Build Progress

- [x] 0.1 — toolchain + empty addon — 2026-07-01
- [x] 0.2 — root menu — 2026-07-01
- [x] 1.1 — site preferences — 2026-07-02
- [ ] 1.2 — fuel products
...
```

This file is also what you hand Claude Code at the start of each session (alongside `CLAUDE.md`) so it knows exactly where you are without you re-explaining — *"Continue from PROGRESS.md, next task is 1.2."*

---

*End of Document*

**Document Version:** 1.0.0
**Companion documents:** `Odoo-FMS-Implementation-Guide.md`, `Odoo-PTS2-Integration-Guide.md`, `Odoo-FMS-Developer-Deployment-Maintenance-Guide.md`
