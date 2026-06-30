# Odoo for Go Developers — FMS Implementation, Deployment & Maintenance Guide

**Audience:** Solo developer, strong in Go, new to Odoo/Python, building and running the `fms` addon
**Tooling assumption:** Claude Code CLI is your primary pair-programmer
**Companion documents:** `Odoo-FMS-Implementation-Guide.md`, `Odoo-PTS2-Integration-Guide.md`

---

## Table of Contents

1. [How to Read This Guide](#1-how-to-read-this-guide)
2. [Odoo's Mental Model, Explained for a Go Developer](#2-odoos-mental-model-explained-for-a-go-developer)
3. [Local Development Environment](#3-local-development-environment)
4. [Project & Addon Structure](#4-project--addon-structure)
5. [The Odoo ORM — A Go Developer's Field Guide](#5-the-odoo-orm--a-go-developers-field-guide)
6. [Views, Actions, Menus — Odoo's "Frontend" Without You Writing JS](#6-views-actions-menus--odoos-frontend-without-you-writing-js)
7. [Security: Groups, ACLs, Record Rules](#7-security-groups-acls-record-rules)
8. [Building FMS Step by Step](#8-building-fms-step-by-step)
9. [Working Effectively With Claude Code on This Codebase](#9-working-effectively-with-claude-code-on-this-codebase)
10. [Debugging Odoo](#10-debugging-odoo)
11. [Testing](#11-testing)
12. [Git Workflow & Code Review Discipline](#12-git-workflow--code-review-discipline)
13. [Deployment](#13-deployment)
14. [Docker Compose Reference Stack](#14-docker-compose-reference-stack)
15. [Backups & Disaster Recovery](#15-backups--disaster-recovery)
16. [Upgrades & Migrations](#16-upgrades--migrations)
17. [Monitoring & Operations](#17-monitoring--operations)
18. [Performance Tuning](#18-performance-tuning)
19. [Common Pitfalls for Go Developers](#19-common-pitfalls-for-go-developers)
20. [Day-2 Maintenance Playbook](#20-day-2-maintenance-playbook)
21. [Reference Cheat Sheets](#21-reference-cheat-sheets)
22. [Appendix: CLAUDE.md Template for This Repo](#22-appendix-claudemd-template-for-this-repo)

---

## 1. How to Read This Guide

You already know how to build production systems — you've done it in Go. What you don't yet have is the *Odoo-specific vocabulary and conventions*. This guide is written to map every new Odoo concept onto something you already understand from Go/Postgres/systemd-style deployments, then gives you the concrete, copy-pasteable workflow to build, debug, test, ship, and maintain the FMS addon as a single developer.

Three things make this project specifically tractable for you:

1. **Odoo is "just" a Python web app on top of Postgres with a heavy code-generation layer (the ORM) and a declarative UI layer (XML views).** Once you see the shape of that, most of Odoo's "magic" stops looking magic.
2. **You're building one addon (`fms`), not modifying Odoo core.** Almost everything you do lives in one directory tree you fully control and that survives Odoo upgrades if written correctly.
3. **Claude Code is extremely good at Odoo boilerplate** (model scaffolding, view XML, security CSV rows, manifest wiring) — the repetitive 80% Odoo asks of you. Your job is to *direct* it correctly, review its output against the patterns in this guide, and own the 20% that's actual business logic (the meter-validation engine, the wetstock formulas, the PTS-2 controller).

---

## 2. Odoo's Mental Model, Explained for a Go Developer

### 2.1 The rough architecture analogy

| Go web service concept | Odoo equivalent |
|---|---|
| `struct` + GORM/sqlc model | `models.Model` class (`fms_shift.py`) |
| DB migration file (`golang-migrate`) | **Auto-generated.** Odoo's ORM reads your Python field declarations and runs `ALTER TABLE` itself on module install/upgrade. You almost never hand-write SQL migrations for new fields. |
| `net/http` handler + router | `http.Controller` + `@http.route` (only needed for webhooks like the PTS-2 receiver) |
| HTML templates (`html/template`) | XML **views** (declarative, not templates you "render" yourself — more like a UI schema the framework interprets) |
| Middleware / auth middleware | Odoo's `ir.rule` (row-level) + `ir.model.access.csv` (model-level) — declarative, not code you write per-request |
| `go test` | Odoo's `TransactionCase` (each test runs in a DB transaction that's rolled back — like `BEGIN; ...; ROLLBACK;` per test) |
| `cmd/myservice/main.go` + flags | `odoo-bin -c odoo.conf` |
| `Makefile` / `go build` | There's no compile step — Python is interpreted. You restart the server (or use `-u` to upgrade) to pick up changes. |
| Dependency injection container | Odoo's `self.env` — an object giving you access to *every* model and the current user/company/context, available in nearly every method |
| `interface{}`/generics-based plugin system | Odoo's `_inherit` mechanism — you "monkey-patch" existing models (e.g. `pos.order`) by declaring a new Python class with the same `_name` but `_inherit` instead, and your fields/methods get merged in at runtime |

### 2.2 The big mental shift: **the ORM *is* your schema**

In Go, you'd write a migration, then a struct, then wire them with reflection tags. In Odoo, you write **one Python class**, and:

- The table is created/altered automatically (`ir.model`/`ir.model.fields` introspect your class)
- The list view, form view (if not customized) get reasonable defaults
- CRUD endpoints exist for free (JSON-RPC/XML-RPC, used by the web client)

This means: **adding a field to a model file and restarting Odoo with `-u fms` is roughly equivalent to writing+running a Go migration.** That's the single most important habit to build.

### 2.3 What "no compile step" really means for you

Python is interpreted. Odoo's server process imports your addon's Python files once at startup (or on `-u <module>` for hot-reload-like behaviour during dev, with `--dev=all` for actual file-watching auto-reload). There is no Go-style compiler catching type errors before runtime — **this is the single biggest risk for a Go developer**, because the safety net you're used to (the compiler) does not exist here. Compensate with:

- Type hints (`def foo(self, x: int) -> bool:`) — Odoo's own code doesn't use these much, but you should, and Claude Code will both write and respect them
- `mypy` as an opt-in static checker (works imperfectly with Odoo's metaclass magic, but catches real bugs)
- Tests (§11) doing the job your compiler would in Go
- Running `odoo-bin --dev=all` locally so you get tracebacks immediately on every request rather than silent corruption

### 2.4 Odoo's three permission layers (this trips up everyone, not just Go devs)

1. **`ir.model.access.csv`** — "can this *group* do CRUD on this *model* at all?" (coarse, model-level — like a Go middleware checking `role == "admin"` before hitting any handler for `/shifts/*`)
2. **`ir.rule`** — "which *rows* of this model can this *user* see/write?" (row-level — like adding `WHERE company_id = ANY($1)` to every query, but the framework injects it for you)
3. **Field-level `groups=` attribute** on a field or button in a view — "is this *specific field/button* visible to this group?" (UI-level only — does **not** stop someone from writing the field via RPC, only hides it in the form)

A request is denied if it fails layer 1 or 2. Layer 3 is cosmetic. **If something works in the UI but a test or RPC call bypasses it, you forgot layer 1 or 2 — never rely on layer 3 for real security.**

### 2.5 Odoo's "environment" object — your dependency-injection container

Almost every method you write is a method *on a model class*, and inside it you have `self`. `self` is a *recordset* (like a slice of structs, even when it has one element — Odoo never gives you a "bare" single record, always a recordset of length 0, 1, or N) and `self.env` is the gateway to everything else:

```python
self.env["fms.shift"]              # the model "fms.shift" (like calling a repository)
self.env["fms.shift"].browse(42)   # fetch by id (no DB hit until you access a field — lazy, like a cursor)
self.env["fms.shift"].search([...])  # like SELECT ... WHERE ...
self.env.user                      # current logged-in res.users record
self.env.company                   # current active company
self.env.context                   # ambient dict of request-scoped hints (timezone, lang, default values...)
self.env.cr                        # the raw psycopg2 cursor, for when you need real SQL
```

Think of `self.env` as "the request-scoped context object you'd normally thread through every Go function call" — except Odoo makes it ambient/implicit via `self`.

---

## 3. Local Development Environment

### 3.1 What you need installed

```bash
# Python (Odoo 17 needs 3.10+; Odoo 18 needs 3.10+ too)
python3 --version

# PostgreSQL (Odoo needs a Postgres superuser-ish role, or at least CREATEDB)
sudo apt install postgresql postgresql-contrib

# System deps Odoo's Python packages need to compile (Pillow, psycopg2, lxml, etc.)
sudo apt install build-essential python3-dev libxml2-dev libxslt1-dev \
    libldap2-dev libsasl2-dev libssl-dev libpq-dev libjpeg-dev zlib1g-dev \
    node-less wkhtmltopdf

# Node, for asset bundling (Odoo's web client build step)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g rtlcss
```

> **Go-dev framing:** this is the equivalent of `apt install postgresql && go mod download` — one-time machine setup, not something you repeat per project.

### 3.2 Get Odoo itself

You do **not** fork or vendor Odoo core. Treat it like a dependency you `go get` once and pin a version of:

```bash
git clone --branch 17.0 --depth 1 https://github.com/odoo/odoo.git /opt/odoo17
python3 -m venv /opt/odoo17/.venv
source /opt/odoo17/.venv/bin/activate
pip install --upgrade pip wheel
pip install -r /opt/odoo17/requirements.txt
```

This venv is your "Go toolchain install" — separate from your addon source, which lives in its own git repo.

### 3.3 Your addon repo layout (separate git repo from Odoo core)

```
~/code/awo-fms/                 ← THIS is your git repo, like a Go module root
├── addons/
│   └── fms/                    ← the addon described in the FMS Implementation Guide
├── odoo.conf
├── docker-compose.yml
├── Makefile
├── scripts/
│   ├── dev_up.sh
│   ├── shell.sh
│   └── reset_db.sh
├── CLAUDE.md                   ← see §22
└── .gitignore
```

Never edit `/opt/odoo17` itself. Your `odoo.conf`'s `addons_path` simply lists both directories:

```ini
[options]
addons_path = /opt/odoo17/addons,/home/you/code/awo-fms/addons
admin_passwd = change_me_dev_only
db_host = localhost
db_port = 5432
db_user = odoo
db_password = odoo
xmlrpc_port = 8069
logfile = /home/you/code/awo-fms/.logs/odoo.log
log_level = info
dev_mode = reload,qweb,werkzeug,xml
```

### 3.4 Database setup

```bash
sudo -u postgres createuser -s odoo
sudo -u postgres psql -c "ALTER USER odoo PASSWORD 'odoo';"
createdb -O odoo shell_maanzoni_dev
```

> **Go-dev framing:** one Postgres database per "environment" (dev/test/staging/prod), exactly like you'd do for a Go service. Odoo does *not* require one DB per tenant/company — multi-company in Odoo is rows in tables filtered by `company_id`, all inside **one** database. Don't reach for "one DB per station" — that's the ERPNext/Frappe pattern (separate site DBs), not the Odoo one.

### 3.5 First boot

```bash
source /opt/odoo17/.venv/bin/activate
python3 /opt/odoo17/odoo-bin -c odoo.conf -d shell_maanzoni_dev -i base --stop-after-init
# then start it for real:
python3 /opt/odoo17/odoo-bin -c odoo.conf -d shell_maanzoni_dev --dev=all
```

Visit `http://localhost:8069`, log in as `admin`/the password you set during the DB creation wizard. This is your local "dev server with hot reload" — `--dev=all` watches Python files and auto-reloads workers, and auto-reloads QWeb/XML templates without a restart.

### 3.6 Makefile — your `go run`/`go test` equivalent

```makefile
ODOO := /opt/odoo17/.venv/bin/python3 /opt/odoo17/odoo-bin
CONF := odoo.conf
DB   := shell_maanzoni_dev

.PHONY: run install upgrade shell test test-one reset

run:
	$(ODOO) -c $(CONF) -d $(DB) --dev=all

install:
	$(ODOO) -c $(CONF) -d $(DB) -i fms --stop-after-init

upgrade:
	$(ODOO) -c $(CONF) -d $(DB) -u fms --stop-after-init

shell:
	$(ODOO) -c $(CONF) -d $(DB) shell --shell-interface=ipython

test:
	$(ODOO) -c $(CONF) -d $(DB)_test -i fms --test-tags fms --stop-after-init

test-one:
	$(ODOO) -c $(CONF) -d $(DB)_test --test-tags /fms:$(T) --stop-after-init

reset:
	dropdb --if-exists $(DB) && createdb -O odoo $(DB) && $(MAKE) install
```

`make upgrade` is your **single most-used command** during FMS development — it's the equivalent of `go build && go run` after every model change.

---

## 4. Project & Addon Structure

This is the exact structure from the FMS Implementation Guide §7.2, with notes on *why* each piece exists, Go-dev framing in brackets:

```
addons/fms/
├── __init__.py                 # imports models/, controllers/, wizards/ packages [like main.go's import block]
├── __manifest__.py             # addon metadata + dependency list + data file load order [like go.mod + an install script]
├── controllers/                # HTTP endpoints (only for PTS-2 webhook) [net/http handlers]
├── models/                     # business logic + ORM model classes [your domain package]
├── wizards/                    # TransientModel-backed "forms that do an action" [one-shot RPC-handler-with-a-form]
├── report/                     # SQL-view-backed reporting models [materialized views / read models]
├── data/                       # XML/CSV seed data loaded on install (cron jobs, sequences) [migration seed data]
├── security/                   # ir.model.access.csv + ir.rule XML [authz policy as data]
├── views/                      # XML UI definitions [your "frontend", but declarative]
├── tests/                      # TransactionCase test classes [your _test.go files]
└── static/src/js               # optional OWL components for custom widgets [your frontend JS, only if needed]
```

### 4.1 `__manifest__.py` — read this like a `go.mod` + "load order file"

```python
{
    "name": "Forecourt Management System (FMS)",
    "version": "17.0.1.0.0",
    "depends": ["stock", "point_of_sale", "account", "hr", "purchase", "sale", "mail"],
    "data": [
        # ORDER MATTERS. Security first (groups must exist before rules reference them),
        # then data, then views (views can reference actions/menus defined earlier in this list).
        "security/fms_security_groups.xml",
        "security/ir.model.access.csv",
        "security/fms_security_rules.xml",
        "data/ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "views/fms_shift_views.xml",
        "views/fms_menus.xml",
    ],
    "installable": True,
    "application": True,
}
```

> **Gotcha:** unlike Go's import graph (resolved by the compiler), `data` file order is **entirely your responsibility**. If a view references a menu's `parent` that's declared later in the list, install fails. Claude Code is good at getting this right if you ask it to check the manifest order whenever you add a new XML file — make this an explicit instruction in `CLAUDE.md` (§22).

### 4.2 `models/__init__.py` — Python's version of re-exporting your package

```python
from . import fms_shift
from . import fms_meter_reading
from . import fms_meter_validation_result
from . import fms_tank_dip_reading
from . import fms_cashier_session
from . import fms_cash_event
from . import fms_fuel_delivery_dip
from . import fms_shift_reconciliation
from . import fms_drive_off_record
from . import fms_site_preferences
from . import pos_order        # _inherit extension
from . import account_move     # _inherit extension
from . import stock_picking    # _inherit extension
from . import stock_location   # _inherit extension
from . import product_template # _inherit extension
from . import hr_employee      # _inherit extension
```

Every new model file you create **must** be added here, or it silently never loads (no error — it just doesn't exist). This is the single most common "why doesn't my new field show up" bug for newcomers. Tell Claude Code explicitly: *"after creating a new model file, always add the import to models/__init__.py"* — put this in `CLAUDE.md`.

---

## 5. The Odoo ORM — A Go Developer's Field Guide

### 5.1 Recordsets are not pointers, not slices — they're a third thing

```python
shift = self.env["fms.shift"].browse(42)   # recordset of (at most) 1 record, lazy
shifts = self.env["fms.shift"].search([])  # recordset of N records
shift.name                                  # if len==1, returns the scalar value
shifts.name                                 # !! if len>1, raises an error — fields only resolve on singleton recordsets
shifts.mapped("name")                       # the correct way to get a list of values across many records
for s in shifts:                            # iterating gives you singleton recordsets, one per record
    print(s.name)
```

**Go analogy:** think of a recordset as `[]T` where `T` has no public fields — you can only call methods on it, and most of those methods only work if `len(slice) == 1`. There is no Odoo equivalent of "give me a plain dict/struct out of the ORM" by default — you stay inside recordset-land almost always, and only drop to dicts via `read()` or raw SQL when you need a fast bulk read.

### 5.2 Domains — Odoo's query DSL (think: a tiny embedded `WHERE` clause as nested lists)

```python
self.env["fms.shift"].search([
    ("status", "=", "open"),
    ("company_id", "=", self.env.company.id),
    "|", ("shift_label", "=", "day"), ("shift_label", "=", "evening"),
])
```

A "domain" is a list of 3-tuples (`field`, `operator`, `value`) ANDed together by default, with `&`/`|`/`!` prefix operators for explicit boolean logic (Polish notation — the operator comes *before* its operands, which feels backwards the first few times). This is **not** SQL text — it's a structured AST that the ORM compiles to SQL, and it's also what record rules and `domain=` attributes on view fields use. Once you've internalized domains, security rules (`ir.rule`) and dynamic field domains in views are just "the same DSL, different attachment point."

### 5.3 The decorator vocabulary you actually need

| Decorator | Go analogy | When to use |
|---|---|---|
| `@api.model` | A "static-ish" method — called on the model class, not a specific record | Factory-style helpers, e.g. `_get_rate(...)` |
| `@api.depends("field_a", "field_b")` | A method that recomputes whenever `field_a`/`field_b` change — like a `sync.Once`-guarded cache invalidated by specific inputs | Any `compute=` field |
| `@api.constrains("field")` | A validator run automatically after write/create on that field — like a struct validation tag, but executed as real code, after the DB write | Business-rule guards (e.g. "closing reading can't be less than opening") |
| `@api.onchange("field")` | UI-only, fires in the *browser* before save, never on server-side writes (e.g. import, RPC) | Pre-filling form fields live as the user types — cosmetic only, **never** put real validation only in an `onchange` |
| `@api.model_create_multi` | Marks `create()` as accepting a list of dicts (Odoo 17+ convention) | Always use this signature for `create()` overrides in new code |

> **Pitfall specific to Go devs:** `@api.onchange` *looks* like validation but is **not** enforced server-side. If you only validate in an `onchange`, an API/import/RPC caller bypasses it completely. Real validation always belongs in `@api.constrains` or in `write()`/`create()` overrides — exactly the discipline from the FMS guide's `fms.shift.write()` override and `fms.meter.reading._check_closing_not_below_opening()`.

### 5.4 `compute` fields: the closest thing to a Go computed property, with a twist

```python
expected_cash = fields.Monetary(compute="_compute_expected_cash", store=True)

@api.depends("elec_vol_sold", "shift_rate")
def _compute_expected_cash(self):
    for rec in self:
        rec.expected_cash = rec.elec_vol_sold * rec.shift_rate
```

- `store=True` → persisted to the DB column, recomputed and rewritten whenever a dependency changes (good for fields you'll filter/sort/sum in list views and SQL reports)
- `store=False` (default) → computed on read only, never hits the DB (good for cheap, rarely-queried derived values)
- **Always loop over `self`** inside a compute method — Odoo may call it with a recordset of many records at once (batched for performance), never assume `self` is a singleton inside a compute.

### 5.5 `write()`/`create()` overrides — your "before/after save hooks"

```python
def write(self, vals):
    # vals is a dict of {field_name: new_value} for ALL records in self —
    # NOT per-record. If you need per-record old values, fetch them BEFORE calling super().
    if "status" in vals:
        for rec in self:
            old_status = rec.status
            # ... validate transition using old_status vs vals["status"]
    return super().write(vals)
```

**Crucial gotcha:** `self` inside `write()` can be a recordset of *many* records being updated with the *same* `vals` dict simultaneously (e.g. a bulk "Mark as Closed" action selected on 10 list-view rows). Always loop per-record when you need each record's *current* (pre-write) state; `vals` itself is shared across all of them.

### 5.6 Raw SQL — when and how

Use `self.env.cr.execute(...)` for: HQ-wide aggregate reports across thousands of shifts (§27.2 in the FMS guide), and SQL-view-backed reporting models (`_auto = False`). **Never** use raw SQL for anything that should respect record rules/multi-company security (§16 in the FMS guide) — you must add the company filter yourself, the ORM's automatic filtering does not apply to raw cursor queries.

```python
self.env.cr.execute("""
    SELECT id, name FROM fms_shift
    WHERE company_id = ANY(%(company_ids)s) AND status = %(status)s
""", {"company_ids": self.env.companies.ids, "status": "open"})
rows = self.env.cr.dictfetchall()
```

Always use `%(name)s` placeholders with a params dict (psycopg2 parameter binding) — **never** f-string/`.format()` user input into SQL. This is the same SQL-injection discipline you already have from Go's `database/sql` placeholder rules.

---

## 6. Views, Actions, Menus — Odoo's "Frontend" Without You Writing JS

You will spend a lot of time in XML. This is unfamiliar if you're used to building APIs and letting a separate frontend (React/whatever) consume them, but Odoo's web client is generic — it renders *any* model's CRUD UI by interpreting XML view definitions you declare. You are not writing HTML/CSS/JS for 95% of FMS.

### 6.1 The four pieces that always go together

```xml
<!-- 1. A form view: how one record renders -->
<record id="view_fms_shift_form" model="ir.ui.view">
    <field name="name">fms.shift.form</field>
    <field name="model">fms.shift</field>
    <field name="arch" type="xml">
        <form>
            <header>
                <field name="status" widget="statusbar" statusbar_visible="draft,open,readings_captured,closing,closed"/>
            </header>
            <sheet>
                <group>
                    <field name="company_id"/>
                    <field name="shift_date"/>
                    <field name="shift_label"/>
                </group>
                <notebook>
                    <page string="Meter Readings">
                        <field name="meter_reading_ids"/>
                    </page>
                </notebook>
            </sheet>
        </form>
    </field>
</record>

<!-- 2. A list ("tree") view: how many records render in a table -->
<record id="view_fms_shift_list" model="ir.ui.view">
    <field name="name">fms.shift.list</field>
    <field name="model">fms.shift</field>
    <field name="arch" type="xml">
        <list>
            <field name="name"/>
            <field name="shift_date"/>
            <field name="status"/>
        </list>
    </field>
</record>

<!-- 3. An action: "what happens when you click this menu item" -->
<record id="action_fms_shift" model="ir.actions.act_window">
    <field name="name">Shifts</field>
    <field name="res_model">fms.shift</field>
    <field name="view_mode">list,form</field>
</record>

<!-- 4. A menu item: where it appears in the nav -->
<menuitem id="menu_fms_shift" name="Shifts" parent="menu_fms_shift_ops"
          action="action_fms_shift" sequence="10"/>
```

**Go-dev framing:** the `<list>` view is your default `GET /shifts` JSON-array-rendered-as-table; the `<form>` view is your default `GET /shifts/:id` rendered as an editable form; the `action` is your route registration; the `menu` is your nav-bar link. You declare all four, the framework wires the HTTP/RPC layer for you.

### 6.2 Things that bite Go developers in views

- **XML IDs must be globally unique within your addon** (`view_fms_shift_form`). Collisions across addons are why Odoo prefixes everything with the module name implicitly when referenced as `fms.view_fms_shift_form` from elsewhere — but inside your own addon's XML you refer to them unprefixed.
- **`field` order inside `<group>` controls layout, not data.** Two fields side-by-side vs stacked is just XML nesting — no CSS to write.
- **Smart buttons** (the little stat buttons top-right of a form, e.g. "3 Meter Readings") are just another `<button type="object">` calling a Python method that returns an `ir.actions.act_window` dict — same pattern as any other button.
- **`invisible`/`readonly`/`required` attributes accept domain-like expressions**, e.g. `invisible="status != 'open'"` (Odoo 17+ syntax) — this is the views layer reusing the same domain DSL from §5.2, not a separate templating language.

### 6.3 When you actually need to write JavaScript

Only for: custom interactive widgets (e.g. the HQ dashboard charts in FMS §28.3), or behaviour the standard widgets genuinely can't express. For 95% of FMS — shift forms, meter reading grids, reconciliation review screens — the standard `<form>`/`<list>` widgets (including editable list views, which behave like spreadsheet-style inline-editable tables) are enough. **Don't reach for OWL/JS until you've confirmed the standard widget set can't do it** — this is the opposite instinct from Go-web-dev, where you'd typically own the whole frontend.

---

## 7. Security: Groups, ACLs, Record Rules

Revisit §2.4. In code, this is what the three layers look like:

```xml
<!-- security/fms_security_groups.xml -->
<record id="group_site_cashier" model="res.groups">
    <field name="name">FMS / Site Cashier</field>
    <field name="category_id" ref="base.module_category_operations"/>
</record>
<record id="group_site_supervisor" model="res.groups">
    <field name="name">FMS / Site Supervisor</field>
    <field name="implied_ids" eval="[(4, ref('group_site_cashier'))]"/>
</record>
```

`implied_ids` is Odoo's group inheritance — a supervisor automatically gets everything a cashier gets, plus more, **the same idea as Go's interface embedding**, just declared as data instead of code.

```csv
# security/ir.model.access.csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_fms_shift_cashier,fms.shift.cashier,model_fms_shift,fms.group_site_cashier,1,0,0,0
access_fms_shift_supervisor,fms.shift.supervisor,model_fms_shift,fms.group_site_supervisor,1,1,1,0
```

```xml
<!-- security/fms_security_rules.xml -->
<record id="fms_shift_company_rule" model="ir.rule">
    <field name="name">FMS Shift: multi-company</field>
    <field name="model_id" ref="model_fms_shift"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>
```

**Testing checklist whenever you add a new model:** does it have an `ir.model.access.csv` row for every group that should touch it? Does it need an `ir.rule`? (Anything with a `company_id` field almost always does — copy the pattern above.) Claude Code will generate these correctly if you point it at an existing model's security rows as a template and say "do the same for `fms.cash.event`".

---

## 8. Building FMS Step by Step

This is the order that minimizes "why doesn't this work" debugging, going from the FMS Implementation Guide's model list:

1. **Scaffold the addon skeleton** (`__manifest__.py`, empty `models/__init__.py`, `security/`, `views/fms_menus.xml` with just the root menu). Install it (`make install`). Confirm it appears in Apps with no errors before writing a single model.
2. **Build `fms.site.preferences` first.** It's the simplest model (no state machine, no relations to anything but `res.company`), and gives you a model+view+menu+security round-trip to validate your whole toolchain works.
3. **Build `fms.shift`** with just the basic fields and the state machine — no meter readings yet. Get open/close transitions working with dummy data.
4. **Build `fms.pump`, `fms.pump.nozzle`, `fms.tank.calibration.chart`** — the static configuration models, no business logic.
5. **Build `fms.meter.reading`** with its constraints. Write the unit tests from FMS Guide §20.1 *before or alongside* this model — they pin down the exact thresholds and prevent regressions as you iterate.
6. **Build `fms.tank.dip.reading`** and the calibration interpolation.
7. **Build `fms.cashier.session` / `fms.cash.event`.**
8. **Wire the `pos.order` / `account.move` / `stock.picking` `_inherit` extensions** (FMS Guide §8) — these touch *existing* Odoo models, so test carefully against a fresh POS session to make sure you haven't broken core POS flows.
9. **Build `fms.shift.reconciliation`** and the wetstock/cash formulas — port the test cases from FMS Guide §20.2 first, then make them pass.
10. **Build the journal-entry posting** (`post_shift_journal_entry`) last — it's the highest-blast-radius piece (real accounting entries), and easiest to get right once everything feeding it is already tested.
11. **Build the PTS-2 controller** (`controllers/pts2.py`) only after the manual workflow above is fully working end-to-end — the PTS-2 controller just creates `fms.forecourt.transaction` records, which is a thin layer on top of everything else.
12. **Build reports/dashboard last.** They're read-only views over data that already exists; there's no reason to build them before the data model is stable.

This order matches the FMS Guide's own Phase 1→2→3 plan (§19), just broken into smaller, independently-testable increments.

---

## 9. Working Effectively With Claude Code on This Codebase

### 9.1 Set up `CLAUDE.md` first (template in §22)

Claude Code reads `CLAUDE.md` automatically at the start of a session in this repo. Put project-specific conventions there once, and you stop having to repeat them in every prompt. Things worth pinning: addon name, manifest data-file ordering rule, "always add new model imports to `models/__init__.py`", the company-record-rule pattern, and where the two companion markdown guides live (so Claude Code can `cat`/grep them for the canonical field lists instead of guessing).

### 9.2 Prompting patterns that work well for Odoo specifically

**Good — anchored to an existing pattern:**
> "Create `fms.fleet.card` following the exact same structure as `fms.cash.event` in `models/fms_cash_event.py` — same security/view/menu wiring pattern, fields per FMS Implementation Guide §7.11."

**Good — explicit about which guide section is the spec:**
> "Implement the `compute_tank_wetstock` method exactly as specified in Odoo-FMS-Implementation-Guide.md §13.1 — don't change the variance classification thresholds."

**Risky — too open-ended for a framework Claude Code might pattern-match to ERPNext/Django instead of Odoo's actual idioms:**
> "Add a wetstock report" — likely to get *a* working implementation, but maybe not matching the existing `_auto = False` SQL-view pattern already used elsewhere in the addon. Always reference an existing sibling file as the pattern to follow.

### 9.3 Use Claude Code to explain *why* something failed, not just to fix it

Odoo tracebacks are often deep (ORM → ORM → ORM → your code), and the actual cause is frequently 1–2 frames from the bottom, not the top exception. Paste the **full** traceback into Claude Code rather than summarizing it — it's much better at spotting "oh, this is a missing `ir.model.access.csv` row, not a code bug" when it can see the actual `AccessError` text, vs. you paraphrasing it as "I get a permission error."

### 9.4 Always run `make upgrade` yourself after Claude Code changes a model

Don't ask Claude Code to "verify it works" by reading the code — Python's lack of compile-time checking means the only real verification is running it. Treat every model/view change exactly like you'd treat a Go diff: you build and run it. A useful loop:

```
1. Ask Claude Code for the change.
2. Run: make upgrade 2>&1 | tail -50
3. If it fails, paste the error back to Claude Code verbatim.
4. If it succeeds, manually click through the affected screen once.
5. Run the relevant test (make test-one T=TestMeterValidation).
6. Commit.
```

### 9.5 Let Claude Code write the boilerplate, you own the formulas

The wetstock/meter-validation/cash-reconciliation math in this project is the business-critical part — the exact thresholds, rounding, and classification logic in the FMS guide (§4, §13). Treat that code the way you'd treat the core algorithm in a Go service: write/review it line-by-line yourself, with Claude Code as a second pair of eyes checking against the test cases, rather than delegating the formula logic wholesale and trusting it blind. The CRUD/views/security wiring around it is exactly the opposite — fully delegate that to Claude Code and spend your review time on the math.

### 9.6 Keep a `docs/decisions.md` for things you deviated from in the two guides

Real implementation will diverge from the two companion guides in small ways (exact field names, a different report approach, a library version bump). Note these as you go, in a file Claude Code can read in future sessions, so it doesn't "correct" your deliberate deviations back to the original guide's wording.

---

## 10. Debugging Odoo

### 10.1 Where the logs are and how to read them

```bash
tail -f .logs/odoo.log
```

A typical traceback looks scary but reads bottom-up like a Go panic: the actual `raise` is near the bottom, everything above it is the ORM call stack that led there. Look for:
- `psycopg2.errors.*` → a DB constraint violation (often a missing required field, or a unique-constraint hit — same as a Go `pq.Error`)
- `odoo.exceptions.ValidationError`/`UserError` → your own (or another addon's) `@api.constrains`/explicit `raise` firing — read the message, it's meant for humans
- `odoo.exceptions.AccessError` → §2.4/§7 permission denial — check `ir.model.access.csv` and `ir.rule` for the model+group in question

### 10.2 `--dev=all` is your best debugging friend

It enables:
- Auto-reload on Python file changes (no manual restart for most changes — though model *field* changes still need `-u fms` to alter the DB schema; pure method-body changes reload live)
- A debugger that drops into `pdb` on unhandled exceptions if you also pass `--dev=pdb`
- Verbose ORM query logging if you bump `log_level` to `debug_sql` (very noisy, but invaluable for "why is this 10x slower than expected" — same instinct as `EXPLAIN ANALYZE` debugging in Go services)

### 10.3 The Odoo shell — your `go run`-a-snippet / Postgres-psql-with-superpowers tool

```bash
make shell
```

Drops you into an IPython shell with `env` (an `Environment` bound to your DB) already available:

```python
>>> shift = env["fms.shift"].search([], limit=1)
>>> shift.status
'open'
>>> shift.write({"status": "readings_captured"})
>>> env.cr.commit()   # shell doesn't auto-commit; explicit commit needed to persist changes outside a request
```

Use this constantly during development to poke at data, test a formula interactively, or fix a bad record without writing a one-off script — the direct equivalent of opening `psql` against your dev DB, except you get the full ORM/business-logic layer instead of raw SQL.

### 10.4 Inspecting what the ORM actually generated

```python
>>> print(env["fms.shift"].search([("status", "=", "open")])._where_calc([("status", "=", "open")]))
```

Or simpler: turn on `debug_sql` log level temporarily and watch the log file while you trigger the action in the browser — you'll see the literal SQL Odoo ran, which is often the fastest way to confirm a record rule or domain is doing what you think.

### 10.5 Browser-side debugging

Append `?debug=1` to the Odoo URL (or enable Developer Mode under Settings) to unlock: "View Fields" (inspect any field's technical name/type directly in the form — crucial for figuring out what to put in a domain or view), "Edit Action"/"Edit View" (open the XML of whatever you're looking at directly from the UI), and an in-browser ORM/RPC inspector under the bug icon in the top bar.

---

## 11. Testing

### 11.1 The mental model

`TransactionCase` (Odoo's base test class) wraps each test method in a DB transaction that's rolled back at the end — conceptually identical to wrapping a Go integration test in `BEGIN`/`ROLLBACK`, except Odoo does it for you automatically. You get a real Postgres-backed `env` in every test, not a mock.

```python
from odoo.tests.common import TransactionCase

class TestFmsShift(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create({"name": "Test Station"})

    def test_cannot_have_two_open_shifts(self):
        self.env["fms.shift"].create({
            "company_id": self.company.id, "station_id": self.company.id,
            "shift_date": "2026-05-17", "shift_label": "day", "status": "open",
        })
        with self.assertRaises(ValidationError):
            self.env["fms.shift"].create({
                "company_id": self.company.id, "station_id": self.company.id,
                "shift_date": "2026-05-17", "shift_label": "evening", "status": "open",
            })
```

### 11.2 Running tests

```bash
make test                          # whole fms test suite, against a dedicated *_test DB
make test-one T=TestMeterValidation
```

Always run the full suite (`make test`) before pushing, and the focused one (`make test-one`) constantly while iterating on a specific formula — this is your `go test ./...` vs `go test -run TestFoo` split.

### 11.3 What to actually test, given you're a solo dev with limited time

Prioritize in this order (highest ROI first):
1. **The pure-math formulas** (meter validation, wetstock, cash reconciliation) — these are pure functions in spirit even though they're methods; the test cases already exist verbatim in the FMS guide §20.1/§20.2, just port them
2. **State machine transitions** on `fms.shift` — the allowed/forbidden transitions table is exactly the kind of thing that silently breaks when someone (you, or Claude Code) "simplifies" the code later
3. **Security** — at least one test per model confirming a cashier *cannot* read/write another company's records (catches a missing `ir.rule` immediately, rather than discovering it in production)
4. **The journal-entry balance check** (`total_dr == total_cr` within tolerance) — an unbalanced posting is the single worst possible production bug for this system
5. Everything else, opportunistically, as you have time

### 11.4 Why tests matter more here than in a typical Go project

You don't have the compiler catching "I renamed a field but forgot to update the three other places that referenced the old name." Tests are the only mechanical safety net you have in Python/Odoo, and Claude Code-assisted refactors specifically benefit from a test suite that fails loudly the moment a rename/refactor breaks something it didn't account for — treat the test suite as the contract Claude Code has to satisfy, not optional documentation.

---

## 12. Git Workflow & Code Review Discipline

### 12.1 Repo layout

```
~/code/awo-fms/          ← git repo root (addons/fms is the addon; this repo also holds infra config)
```

Keep `odoo.conf`, `docker-compose.yml`, and deployment scripts in the *same* repo as the addon — for a solo developer, splitting "app code" and "infra code" into separate repos adds coordination overhead with no real benefit at this scale.

### 12.2 Commit discipline

Because there's no compiler, treat **every commit as something that must independently `make upgrade && make test` cleanly** — never commit a half-broken model "to save progress," since the next person reading git history (including future-you, including Claude Code re-reading the repo in a new session) needs every commit to be a coherent, working state. Use `git stash`/WIP branches for genuinely incomplete work instead of broken commits on `main`.

### 12.3 `.gitignore` essentials

```
.venv/
.logs/
*.pyc
__pycache__/
filestore/
sessions/
*.swp
.vscode/
odoo.conf.local
```

Never commit `odoo.conf` with real production secrets (admin password, DB password, PTS-2 HMAC secret) — keep a `odoo.conf.example` checked in and a real `odoo.conf`/`odoo.conf.local` git-ignored, loaded via your deployment process (§13).

### 12.4 Pre-commit checklist (script this — see `scripts/precommit.sh`)

```bash
#!/usr/bin/env bash
set -e
make upgrade
make test
echo "OK to commit."
```

Run this before every commit touching `addons/fms`. It's slower than `gofmt && go vet && go test ./...` but serves exactly the same purpose, and is worth the wait given Python's weaker static guarantees.

### 12.5 Working with Claude Code across multiple sessions

Since Claude Code doesn't retain memory between sessions by default, lean on:
- `CLAUDE.md` (§22) for durable conventions
- `docs/decisions.md` (§9.6) for deviations from the two companion guides
- Small, focused commits with descriptive messages — a future Claude Code session can `git log -p` to reconstruct *why* something is the way it is, faster than you re-explaining it from scratch

---

## 13. Deployment

### 13.1 Production topology (single-server, appropriate for 1–5 sites per FMS Guide §18)

```
                    Internet
                       │
                 ┌─────▼─────┐
                 │  Nginx    │  ← TLS termination, reverse proxy, PTS-2 webhook path
                 └─────┬─────┘
            ┌──────────┼──────────┐
      ┌─────▼────┐ ┌───▼────┐ ┌──▼───────┐
      │ Odoo     │ │ Odoo   │ │PostgreSQL│
      │ (gevent  │ │(workers│ │          │
      │ longpoll)│ │ HTTP)  │ │          │
      └──────────┘ └────────┘ └──────────┘
              all on one VM, managed by systemd
```

### 13.2 systemd unit (the production equivalent of your `make run`)

```ini
# /etc/systemd/system/odoo-fms.service
[Unit]
Description=Odoo FMS (Shell Maanzoni)
After=postgresql.service network.target

[Service]
Type=simple
User=odoo
Group=odoo
ExecStart=/opt/odoo17/.venv/bin/python3 /opt/odoo17/odoo-bin -c /etc/odoo/odoo-fms.conf
Restart=on-failure
RestartSec=5
LimitNOFILE=8192

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now odoo-fms
sudo systemctl status odoo-fms
journalctl -u odoo-fms -f          # equivalent of `journalctl -u your-go-service -f`
```

### 13.3 Production `odoo.conf` differences from dev

```ini
[options]
addons_path = /opt/odoo17/addons,/opt/awo-fms/addons
admin_passwd = <long random value, stored in a secrets manager, never in git>
db_host = localhost
db_user = odoo
db_password = <from secrets manager>
db_name = shell_maanzoni
list_db = False              # hide the DB selector/manager screen from the public internet
proxy_mode = True            # trust X-Forwarded-* headers from Nginx
workers = 4                  # multi-process; 0 (dev default) means single-process, no use in prod
max_cron_threads = 2
limit_time_cpu = 60
limit_time_real = 120
logfile = /var/log/odoo/odoo-fms.log
log_level = info
```

`workers > 0` switches Odoo from its single-threaded dev server to a **prefork multi-process model** (conceptually similar to running multiple instances of a Go service behind a load balancer, except it's one `odoo-bin` process forking workers, not N separate binaries) — required for any real concurrent load. With `workers > 0` you also need a second small process (handled automatically by Odoo) for cron jobs and the longpolling/websocket gateway — `max_cron_threads` controls the former.

### 13.4 Nginx config (production version of the snippet in the FMS Guide §18)

```nginx
upstream odoo {
    server 127.0.0.1:8069;
}
upstream odoo-chat {
    server 127.0.0.1:8072;
}

server {
    listen 80;
    server_name fms.shelldomain.co.ke;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name fms.shelldomain.co.ke;

    ssl_certificate     /etc/letsencrypt/live/fms.shelldomain.co.ke/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fms.shelldomain.co.ke/privkey.pem;

    client_max_body_size 50m;
    proxy_read_timeout 720s;

    location /fms/pts2/receive {
        proxy_pass http://odoo;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
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
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    location ~* /web/static/ {
        proxy_cache_valid 200 60m;
        proxy_pass http://odoo;
    }
}
```

```bash
sudo certbot --nginx -d fms.shelldomain.co.ke
```

### 13.5 First production deploy checklist

```
□  Provision VM per FMS Guide §18 sizing table
□  Install Postgres, create odoo role + production DB
□  Clone Odoo core (pinned tag, e.g. 17.0) to /opt/odoo17
□  Deploy addons/fms to /opt/awo-fms/addons (git clone or rsync from CI, see §13.6)
□  Write /etc/odoo/odoo-fms.conf with production values (NOT checked into git)
□  systemd unit installed, enabled
□  Nginx + certbot configured
□  Run: odoo-bin -c odoo-fms.conf -d shell_maanzoni -i fms --stop-after-init  (first install)
□  systemctl start odoo-fms
□  Log in, set up companies/users/security groups per FMS Guide §6.5–6.6
□  Configure fms.site.preferences for Shell Maanzoni
□  Take a baseline backup (§15) BEFORE entering real production data
```

### 13.6 Deploying updates (your "CD pipeline," even if it's a shell script for now)

```bash
#!/usr/bin/env bash
# scripts/deploy.sh — run from your laptop or a CI runner with SSH access
set -e
ssh odoo@prod-host '
  cd /opt/awo-fms &&
  git fetch origin &&
  git checkout main &&
  git pull &&
  sudo systemctl stop odoo-fms &&
  /opt/odoo17/.venv/bin/python3 /opt/odoo17/odoo-bin \
    -c /etc/odoo/odoo-fms.conf -d shell_maanzoni -u fms --stop-after-init &&
  sudo systemctl start odoo-fms
'
```

This is intentionally simple — a solo developer running one or a few sites doesn't need a Kubernetes-grade CD pipeline. **Take a DB backup immediately before every `-u fms`** (§15) — an addon upgrade that fails partway through can leave the schema in a state that's easier to restore-from-backup than to hand-fix.

---

## 14. Docker Compose Reference Stack

If you'd rather containerize than run bare-metal systemd (closer to how you'd probably ship a Go service):

```yaml
# docker-compose.yml
version: "3.8"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres
    volumes:
      - db_data:/var/lib/postgresql/data
    restart: unless-stopped

  odoo:
    image: odoo:17.0
    depends_on:
      - db
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo
    ports:
      - "8069:8069"
      - "8072:8072"
    volumes:
      - ./addons/fms:/mnt/extra-addons/fms
      - odoo_filestore:/var/lib/odoo
      - ./odoo.conf:/etc/odoo/odoo.conf
    restart: unless-stopped

volumes:
  db_data:
  odoo_filestore:
```

```bash
docker compose up -d
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d shell_maanzoni -i fms --stop-after-init
docker compose logs -f odoo
```

> **Go-dev framing:** this is your `docker-compose.yml` for local/staging exactly like you'd containerize a Go API + Postgres. The official `odoo:17.0` image already bundles the Odoo core + venv — your job is just mounting `addons/fms` in as a volume (dev) or baking it into a custom image `FROM odoo:17.0` + `COPY addons/fms /mnt/extra-addons/fms` (prod, so the image is self-contained and reproducible — closer to a Go static binary).

**Production Dockerfile (self-contained image, no host-mounted addon code):**

```dockerfile
FROM odoo:17.0
COPY addons/fms /mnt/extra-addons/fms
COPY odoo.conf /etc/odoo/odoo.conf
```

Build and push this in CI on every merge to `main`; deploy by pulling the new tag and recreating the container — your actual "CD pipeline" once you outgrow the SSH-script approach in §13.6.

---

## 15. Backups & Disaster Recovery

Odoo state lives in **two places**, both of which must be backed up together (a backup of one without the other is incomplete and will produce broken attachments/missing data on restore):

1. **The PostgreSQL database** — all your structured data
2. **The filestore** — binary attachments (uploaded files, generated PDFs, `ir.attachment` records with `type=binary` stored on disk rather than in the DB), at `~/.local/share/Odoo/filestore/<db_name>/` (bare-metal) or `/var/lib/odoo/filestore/<db_name>/` (Docker)

### 15.1 Manual backup

```bash
#!/usr/bin/env bash
# scripts/backup.sh
set -e
DB=shell_maanzoni
DEST=/backups/$(date +%Y%m%d_%H%M%S)
mkdir -p "$DEST"
pg_dump -U odoo -Fc "$DB" > "$DEST/db.dump"
tar czf "$DEST/filestore.tar.gz" -C /var/lib/odoo/filestore "$DB"
echo "Backup written to $DEST"
```

Run this **before every addon upgrade** (§13.6) and on a daily cron for ongoing protection.

### 15.2 Restore

```bash
dropdb --if-exists shell_maanzoni_restore_test
createdb -O odoo shell_maanzoni_restore_test
pg_restore -U odoo -d shell_maanzoni_restore_test /backups/<ts>/db.dump
tar xzf /backups/<ts>/filestore.tar.gz -C /var/lib/odoo/filestore/
```

**Always restore-test on a `_restore_test` database periodically** (e.g. monthly) — an untested backup is not a backup, exactly the same discipline you'd apply to a Go service's Postgres backups.

### 15.3 Odoo's own backup tooling

The Database Manager UI (`/web/database/manager`, only reachable if `list_db = True`, which you should disable in production per §13.3) can produce a backup zip (DB dump + filestore bundled together) — useful for ad-hoc manual backups during development, but for production rely on the scripted `pg_dump` + filestore tarball approach above, run unattended via cron, not a UI you have to remember to click.

---

## 16. Upgrades & Migrations

### 16.1 Two different kinds of "upgrade" — don't conflate them

1. **Upgrading your own `fms` addon** (you changed a model/view/security file) → `odoo-bin -u fms` — routine, happens every deploy, low risk if your test suite passes first
2. **Upgrading Odoo core itself** (e.g. 17.0 → 18.0) → a major version migration, comparable to a Go major-version language upgrade plus a framework upgrade combined — non-trivial, schedule it deliberately, never do it casually alongside feature work

### 16.2 Adding a field to an existing model (the everyday case)

```python
# Just add the field declaration:
class FmsShift(models.Model):
    _inherit = "fms.shift"
    notes_internal = fields.Text(string="Internal Notes")
```

```bash
make upgrade   # ALTER TABLE happens automatically
```

No migration file to write for the common case. Odoo compares your Python field declarations against `ir.model.fields` and the actual Postgres schema, and issues the necessary `ALTER TABLE ADD COLUMN` itself.

### 16.3 When you *do* need a hand-written migration script

For data transformations the ORM can't infer automatically — e.g. you're renaming a field and need to copy old data into the new column, or backfilling a new required field on existing rows, or restructuring a relationship. Odoo's addon migration framework uses a specific directory convention:

```
addons/fms/migrations/
└── 17.0.2.0.0/          # matches the version bump in __manifest__.py
    ├── pre-migrate.py    # runs BEFORE the ORM applies new field/model definitions
    └── post-migrate.py   # runs AFTER
```

```python
# migrations/17.0.2.0.0/post-migrate.py
def migrate(cr, version):
    cr.execute("""
        UPDATE fms_shift SET notes_internal = reconciliation_notes
        WHERE notes_internal IS NULL
    """)
```

**Go-dev framing:** this is exactly your `golang-migrate` `up.sql` pattern, just keyed by addon version string instead of a sequential migration number, and split into "before the ORM touches the schema" vs "after" phases. Bump `"version"` in `__manifest__.py` whenever you ship a migration script, so Odoo knows to run it on the next `-u fms`.

### 16.4 Odoo core major-version upgrades

For a self-hosted single-tenant deployment like this one, your practical options are:
1. **Manual, on a copy of production data**: stand up the new Odoo core version against a *restored copy* of your production DB, run the new version's built-in `-u all` migration scripts, fix whatever your custom `fms` addon breaks (API changes between major versions do happen — view syntax, deprecated methods), re-test everything, then cut over.
2. **Odoo's official Upgrade service** (paid, hosted) — submits a dump of your DB and gets back a migrated dump. Worth it once you have enough production data/complexity that a DIY migration's risk outweighs the cost.

Either way: **never attempt a core upgrade without a full backup and a tested rollback plan**, and never do it under time pressure (e.g. don't combine it with an urgent feature deadline).

---

## 17. Monitoring & Operations

### 17.1 What to watch, mapped from things you'd already monitor for a Go service

| Signal | Go-world equivalent | How to check in Odoo |
|---|---|---|
| Process up/restarting | `systemctl status` / k8s liveness | `systemctl status odoo-fms`, `journalctl -u odoo-fms` |
| Request latency/errors | APM / structured logs | Odoo's own `log_level=info` logs each request; bump to `debug_sql` temporarily for slow-query hunting |
| DB connection pool exhaustion | `pgx` pool metrics | `db_maxconn` in `odoo.conf`; watch Postgres `pg_stat_activity` for connection counts approaching that limit |
| Background job failures | a job queue's dead-letter queue | `ir.cron` records show `Last execution`/failures in **Settings → Technical → Scheduled Actions**; failures also land in the log file |
| Disk usage | node_exporter | filestore + Postgres data directory — both grow over time, monitor both, not just one |
| PTS-2 device connectivity | a custom heartbeat check | The `fms.pts2.device.last_seen` field + the watchdog cron job (FMS Guide §10.4) — alert if stale > 15 min |

### 17.2 A minimal, solo-developer-appropriate monitoring stack

You don't need a full Prometheus/Grafana stack for 1–5 sites on day one. A pragmatic minimum:
- `systemd`'s own restart-on-failure (already in the unit file, §13.2) as your first line of defense
- A simple cron-based healthcheck hitting `/web/login` and alerting (email/Slack/WhatsApp webhook) on non-200 — five lines of shell, run every 5 minutes
- The `ir.cron` watchdog job (FMS Guide §10.4) already gives you PTS-2-specific alerting for free, since it's part of the addon itself
- Postgres's own `log_min_duration_statement = 2000` (FMS Guide §18) to catch slow queries in the Postgres log without standing up extra infrastructure

Grow into Prometheus/Grafana/Loki only once you have enough sites that "ssh in and tail the log" stops scaling for you personally — there's an official `odoo_exporter`-style community exporter if/when you get there.

### 17.3 Log rotation

```
# /etc/logrotate.d/odoo-fms
/var/log/odoo/odoo-fms.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

---

## 18. Performance Tuning

### 18.1 The two knobs that matter most at small scale

1. **`workers`** in `odoo.conf` — rule of thumb `workers = (CPU cores * 2) + 1`, same formula intuition as sizing a Go HTTP server's `GOMAXPROCS`-bound worker pool, but here it's OS processes, not goroutines (Python's GIL means true parallelism needs separate processes, not threads — this is the single biggest Python-vs-Go runtime difference to internalize: **Odoo's concurrency model is multi-process, not multi-threaded/async**, unlike Go's goroutines).
2. **Postgres connection limits** (`db_maxconn` in `odoo.conf`, and Postgres's own `max_connections`) — each Odoo worker holds its own DB connection(s); too many workers vs too few Postgres connections is a classic self-inflicted outage.

### 18.2 ORM performance traps a Go developer will recognize immediately (N+1 query problem)

```python
# BAD — N+1 queries, one per shift
for shift in shifts:
    print(shift.cashier_id.name)   # each .cashier_id access can trigger a fresh DB hit if not prefetched

# GOOD — prefetch in bulk first
shifts.mapped("cashier_id.name")   # the ORM batches this into one query under the hood
```

Odoo's ORM *does* have an implicit prefetch cache (accessing one record's field often warms the cache for sibling records fetched via the same `search()`), but it's easy to defeat by looping with extra logic in between, or by working with recordsets assembled from multiple separate `search()` calls. **Symptom to watch for:** a list/report screen that gets dramatically slower as record count grows — same root cause and same fix (`mapped`/batch fetch, or a single SQL query with joins for true reporting workloads) as an N+1 bug in a Go service using an ORM like GORM.

### 18.3 When to drop to raw SQL for performance

Anything that needs to aggregate across thousands of `fms.shift` records for an HQ-wide trend report (FMS Guide §27.2.3 and onward) — write it as a SQL-view-backed model (`_auto = False`) rather than looping in Python. This is the same judgment call you'd make in Go: ORM-friendly code for CRUD-shaped work, hand-written SQL for genuinely analytical aggregate queries.

---

## 19. Common Pitfalls for Go Developers

A condensed "things that will bite you specifically because of Go habits":

1. **Forgetting `models/__init__.py` imports.** No compiler error, the model just silently doesn't exist. (§4.2)
2. **Putting validation only in `@api.onchange`.** It's UI-only and never runs for API/import/RPC writes. (§5.3)
3. **Assuming `self` is always one record.** It's a recordset of 0..N; always loop, or call `.ensure_one()` if you genuinely require exactly one.
4. **Mutating `vals` dicts and assuming per-record state.** `write(vals)` is called once with a shared `vals` for potentially many records in `self`. (§5.5)
5. **Writing raw SQL without the company filter.** The ORM's automatic multi-company filtering does *not* apply to `self.env.cr.execute()`. (§5.6, FMS Guide §16)
6. **Treating XML view IDs like Go package-private names.** They're global strings within the addon; collisions are a real risk if you copy-paste view XML carelessly.
7. **Expecting a compiler to catch typos in field names.** A typo'd field name in a domain or `mapped()` call raises at runtime, often deep in ORM internals — write tests, run `make upgrade` often, don't batch up untested changes.
8. **Forgetting that `compute` fields without `store=True` aren't queryable/filterable** in list views or domains the way a stored column is — if you need to filter/sort/sum on it, it must be stored.
9. **Skipping the manifest's `data` list ordering.** Unlike Go's import graph, nothing resolves load order for you — security before data before views, parents before children. (§4.1)
10. **Running a core-Odoo-version upgrade casually.** It's a major-version migration, not a routine deploy — treat it with the same caution as a Go major-version + framework upgrade combined, not as a `go get -u`.
11. **Not realizing Odoo concurrency is multi-process, not goroutine-style.** Tuning `workers` is your `GOMAXPROCS`-equivalent decision, but the cost model (process fork + own DB connection) is heavier per unit than a goroutine. (§18.1)

---

## 20. Day-2 Maintenance Playbook

Quick-reference runbooks for things that *will* happen once Shell Maanzoni (and future sites) are live.

### 20.1 "A shift won't close — Check B keeps failing"

1. Open the shift in Odoo, go to the Meter Validation Results.
2. Identify the failing nozzle (per FMS Guide §4.3 thresholds).
3. Either: physically re-inspect the pump and submit an **Amendment** reading (FMS Guide §7.4), or escalate to KEBS if tampering is suspected.
4. Re-run "Run Meter Validation" from the Close Shift wizard.

### 20.2 "PTS-2 device shows offline / no transactions arriving"

1. Check `fms.pts2.device.last_seen` — how stale is it?
2. SSH/console into the station's network, ping the PTS-2's IP.
3. Check Odoo's log for `401`/HMAC errors on `/fms/pts2/receive` (secret mismatch — PTS-2 Integration Guide §13.4 key-rotation gotcha).
4. Check the PTS-2's own `SERVER.LOG` (PTS-2 Guide §4.11/§14.4) for the failure mode from its side.
5. Worst case: fall back to manual meter-reading entry for the shift (the system is designed to degrade gracefully to this — FMS Guide §17).

### 20.3 "I need to add a new station"

1. Create a new `res.company` with `parent_id` = Shell Kenya Limited.
2. Run through FMS Guide §19 Phase 1 setup for the new company (chart of accounts, products if not already global, tank locations, security/user assignment).
3. Create its `fms.site.preferences` record.
4. Register pumps/nozzles, calibration charts.
5. If using PTS-2: register the new `fms.pts2.device`, configure `fms.pump.configuration` mappings.
6. Run the 2-week parallel-operation period (FMS Guide §19 Phase 3) before relying on it solely.

### 20.4 "A journal entry posted wrong"

**Never edit a posted `account.move` directly** (Odoo blocks/strongly discourages this, same as you'd never hand-edit a ledger). Instead:
1. Create a reversal (`account.move.button_cancel`/`Reverse` action — Odoo's native journal-entry reversal, which posts an offsetting entry rather than deleting history).
2. Fix the underlying source data (the `fms.shift.reconciliation` line that was wrong).
3. Re-run "Compute Reconciliation" and re-post.

### 20.5 "Odoo is slow / unresponsive"

1. `systemctl status odoo-fms` — is it actually up?
2. `journalctl -u odoo-fms -n 200` — recent errors/restarts?
3. Check Postgres: `SELECT * FROM pg_stat_activity WHERE state != 'idle';` — any long-running or stuck queries?
4. Check disk space (`df -h`) — a full disk on the Postgres data directory or filestore will degrade everything.
5. Check `workers` vs `db_maxconn` vs Postgres's `max_connections` — a mismatch here causes intermittent connection-pool exhaustion under load (§18.1).

### 20.6 "I need to give a new employee station access"

1. Create the `hr.employee` record (and `res.users` if they need login access — these are separate models in Odoo; an employee doesn't automatically get a login).
2. Assign the correct FMS security group (§7) — cashier/supervisor/site manager.
3. Restrict `Allowed Companies` on their `res.users` record to just their station (unless HQ staff).

---

## 21. Reference Cheat Sheets

### 21.1 Daily dev loop

```bash
make run                    # start dev server with --dev=all
# ... edit code, browser auto-reloads for most changes ...
make upgrade                 # after any model/security/data XML change
make test-one T=TestX        # focused test while iterating
make test                    # full suite before committing
```

### 21.2 Odoo CLI flags you'll actually use

| Flag | Purpose |
|---|---|
| `-c <file>` | config file |
| `-d <db>` | target database |
| `-i <module>` | install module(s), comma-separated |
| `-u <module>` | upgrade module(s) |
| `--stop-after-init` | run the init/upgrade then exit (for scripted/CI use) |
| `--dev=all` | reload + qweb + werkzeug + xml dev helpers |
| `--test-tags <tags>` | run only matching tests |
| `shell` | drop into an interactive ORM shell |

### 21.3 ORM method quick reference

| Method | Go-ish description |
|---|---|
| `search(domain)` | `SELECT ... WHERE <domain>` → recordset |
| `search_count(domain)` | `SELECT COUNT(*) WHERE <domain>` |
| `browse(ids)` | construct a recordset by primary key, lazily |
| `create(vals_list)` | `INSERT` |
| `write(vals)` | `UPDATE` on every record in `self` |
| `unlink()` | `DELETE` |
| `read(fields)` | bulk-fetch plain dicts (escape hatch out of recordset-land) |
| `mapped("field.path")` | like a `.map()` over a slice, follows relations |
| `filtered(lambda r: ...)` | like a `.filter()` over a slice |
| `sorted(key=...)` | like `sort.Slice` |
| `ensure_one()` | panics (raises) unless `len(self) == 1` |

### 21.4 Where things live on disk

| What | Path (bare-metal) |
|---|---|
| Odoo core | `/opt/odoo17` |
| Your addon | `addons/fms` in your repo, symlinked/added via `addons_path` |
| Config | `/etc/odoo/odoo-fms.conf` (prod), `./odoo.conf` (dev) |
| Logs | `/var/log/odoo/odoo-fms.log` (prod), `.logs/odoo.log` (dev) |
| Filestore | `/var/lib/odoo/filestore/<db_name>/` |
| Sessions | `/var/lib/odoo/sessions/` |

---

## 22. Appendix: CLAUDE.md Template for This Repo

Drop this at the repo root. Adjust as conventions solidify.

```markdown
# CLAUDE.md — awo-fms

## Project
Odoo 17 addon `fms` implementing the Forecourt Management System for Shell
Maanzoni and future Shell Kenya stations. Author is an experienced Go
developer, new to Odoo/Python — explain Odoo-specific idioms briefly when
introducing a new pattern, don't assume prior Odoo knowledge.

## Canonical specs
- `Odoo-FMS-Implementation-Guide.md` — the full model/business-logic spec.
  Field names, thresholds, and formulas in this file are authoritative unless
  `docs/decisions.md` records a deliberate deviation.
- `Odoo-PTS2-Integration-Guide.md` — PTS-2 hardware/protocol spec.
- `docs/decisions.md` — deviations from the above two guides, with reasons.
  Check this before "fixing" something that looks like a deviation.

## Conventions
- Every new model file in `addons/fms/models/` MUST be added to
  `models/__init__.py`, or it silently won't load.
- `__manifest__.py`'s `data` list order matters: security groups → ACLs →
  record rules → data (sequences/cron) → views → menus. Never reorder
  carelessly when adding a new XML file.
- Every model with a `company_id` field needs both an `ir.model.access.csv`
  row per relevant security group AND an `ir.rule` company-filter row,
  following the pattern in `security/fms_security_rules.xml`.
- Validation belongs in `@api.constrains` or `write()`/`create()` overrides —
  never only in `@api.onchange` (that's UI-only and skips API/import writes).
- Raw SQL (`self.env.cr.execute`) must always include an explicit company
  filter (`company_id = ANY(%(company_ids)s)`) — record rules do not apply
  to raw SQL.
- New business-logic methods (meter validation, wetstock, cash reconciliation)
  must have a corresponding test in `tests/`, using the exact reference
  numbers from the Shell Maanzoni 17-05-2026 dataset in the FMS guide where
  applicable.

## Workflow expected from you (Claude)
- After any model/view/security change, tell me to run `make upgrade` myself
  — do not assume the change works just because the code looks correct.
- When implementing something from the FMS guide, quote the section number
  you're implementing from in your response.
- When extending an existing pattern (e.g. "add a new cash event type"),
  find and follow the closest existing analogous model/view/security trio
  rather than inventing a new structure.
- Flag (don't silently fix) any place where my request seems to contradict
  the Golden Rules in FMS Guide §2 (shift-as-unit-of-everything, three
  meters, dual control on cash, etc.) — these are deliberate business
  invariants, not arbitrary choices.

## Commands
- `make run` — dev server
- `make upgrade` — apply model/data changes to the dev DB
- `make test` / `make test-one T=<TestClassName>` — run tests
- `make shell` — interactive ORM shell against the dev DB
```

---

*End of Document*

**Document Version:** 1.0.0
**Audience:** Solo Go developer, new to Odoo, using Claude Code CLI
**Companion documents:** `Odoo-FMS-Implementation-Guide.md`, `Odoo-PTS2-Integration-Guide.md`
