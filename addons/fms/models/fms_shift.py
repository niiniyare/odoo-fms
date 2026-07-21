from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Legal state transitions.  Any write to `state` that is not in this map
# (for the record's current state) is rejected by the write() override.
ALLOWED_TRANSITIONS = {
    "draft":            {"readings_pending"},
    "readings_pending": {"open", "draft"},
    "open":             {"closing"},
    "closing":          {"closed", "open"},
    "closed":           {"disputed"},
    "disputed":         set(),              # terminal — no exit without manual DB fix
}


class FmsShift(models.Model):
    """Operational shift — the primary transactional boundary for FMS.

    Every meter reading, dip reading, POS transaction, cash event, and
    reconciliation entry belongs to exactly one shift.  State transitions
    are enforced by the write() override; arbitrary state writes are rejected.

    Lifecycle:
        draft → readings_pending → open → closing → closed [→ disputed]
    """

    _name = "fms.shift"
    _description = "Forecourt Shift"
    _order = "shift_date desc, shift_label"
    _rec_name = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ── Identity ──────────────────────────────────────────────────────────

    name = fields.Char(
        string="Shift Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        help="Auto-generated shift reference from sequence.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Station / company this shift belongs to.",
    )

    # ── Scheduling ────────────────────────────────────────────────────────

    shift_date = fields.Date(
        string="Shift Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    shift_label = fields.Selection(
        [
            ("morning",   "Morning"),
            ("afternoon", "Afternoon"),
            ("night",     "Night"),
        ],
        string="Shift",
        required=True,
        default="morning",
        tracking=True,
        help="Identifies which of the three daily shift slots this record covers.",
    )

    # ── Status ────────────────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft",            "Draft"),
            ("readings_pending", "Readings Pending"),
            ("open",             "Open"),
            ("closing",          "Closing"),
            ("closed",           "Closed"),
            ("disputed",         "Disputed"),
        ],
        string="State",
        default="draft",
        required=True,
        index=True,
        tracking=True,
        copy=False,
        help="Current lifecycle state.  Transitions are strictly controlled — "
             "see ALLOWED_TRANSITIONS in the model source.",
    )

    # ── Personnel ─────────────────────────────────────────────────────────

    supervisor_id = fields.Many2one(
        "hr.employee",
        string="Supervisor",
        tracking=True,
        help="Employee responsible for this shift.",
    )
    opened_by = fields.Many2one(
        "res.users",
        string="Opened By",
        readonly=True,
        copy=False,
        help="User who transitioned the shift to Open.",
    )
    closed_by = fields.Many2one(
        "res.users",
        string="Closed By",
        readonly=True,
        copy=False,
        help="User who transitioned the shift to Closed.",
    )

    # ── Timing ────────────────────────────────────────────────────────────

    opened_at = fields.Datetime(
        string="Opened At",
        readonly=True,
        copy=False,
        help="Timestamp when the shift was transitioned to Open.",
    )
    closed_at = fields.Datetime(
        string="Closed At",
        readonly=True,
        copy=False,
        help="Timestamp when the shift was transitioned to Closed.",
    )

    # ── Relations (placeholders — wired in later milestones) ─────────────

    cashier_session_ids = fields.One2many(
        "fms.cashier.session",
        "shift_id",
        string="Cashier Sessions",
    )
    meter_reading_ids = fields.One2many(
        "fms.meter.reading",
        "shift_id",
        string="Meter Readings",
    )
    meter_reading_count = fields.Integer(
        string="Meter Readings",
        compute="_compute_meter_reading_count",
    )
    dip_reading_ids = fields.One2many(
        "fms.tank.dip.reading",
        "shift_id",
        string="Dip Readings",
    )
    dip_reading_count = fields.Integer(
        string="Dip Readings",
        compute="_compute_dip_reading_count",
    )
    total_dispensed_litres = fields.Float(
        string="Total Dispensed (L)",
        digits=(16, 3),
        compute="_compute_total_dispensed_litres",
        store=True,
        help="Sum of confirmed closing reading dispensed_litres across all nozzles "
             "in this shift.  Updates automatically when a closing reading is confirmed.",
    )

    # ── Computed helpers ──────────────────────────────────────────────────

    def _compute_meter_reading_count(self):
        for rec in self:
            rec.meter_reading_count = len(rec.meter_reading_ids)

    def _compute_dip_reading_count(self):
        for rec in self:
            rec.dip_reading_count = len(rec.dip_reading_ids)

    @api.depends("meter_reading_ids.dispensed_litres", "meter_reading_ids.state",
                 "meter_reading_ids.reading_type")
    def _compute_total_dispensed_litres(self):
        for rec in self:
            rec.total_dispensed_litres = sum(
                r.dispensed_litres
                for r in rec.meter_reading_ids
                if r.reading_type == "closing" and r.state == "confirmed"
            )

    shift_label_display = fields.Char(
        string="Shift Label",
        compute="_compute_shift_label_display",
        store=False,
    )

    def _compute_shift_label_display(self):
        label_map = dict(self._fields["shift_label"].selection)
        for rec in self:
            rec.shift_label_display = label_map.get(rec.shift_label, "")

    # ── ORM overrides ─────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("fms.shift") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals:
            new_state = vals["state"]
            for rec in self:
                allowed = ALLOWED_TRANSITIONS.get(rec.state, set())
                if new_state not in allowed:
                    raise UserError(
                        _(
                            "Cannot move shift '%(name)s' from '%(from)s' to '%(to)s'.\n"
                            "Allowed transitions from '%(from)s': %(allowed)s.",
                            name=rec.name,
                            **{"from": rec.state},
                            to=new_state,
                            allowed=", ".join(sorted(allowed)) or _("none"),
                        )
                    )
        return super().write(vals)

    # ── Transition actions (called from buttons) ──────────────────────────

    def action_start_readings(self):
        """Draft → Readings Pending."""
        self.write({"state": "readings_pending"})

    def action_open(self):
        """Readings Pending → Open.  Stamps opened_at / opened_by."""
        now = fields.Datetime.now()
        self.write({
            "state":     "open",
            "opened_at": now,
            "opened_by": self.env.uid,
        })

    def action_start_closing(self):
        """Open → Closing."""
        self.write({"state": "closing"})

    def action_close(self):
        """Closing → Closed.  Stamps closed_at / closed_by."""
        now = fields.Datetime.now()
        self.write({
            "state":     "closed",
            "closed_at": now,
            "closed_by": self.env.uid,
        })

    def action_reopen(self):
        """Closing → Open (e.g. supervisor rejects preliminary close)."""
        self.write({"state": "open"})

    def action_mark_disputed(self):
        """Closed → Disputed."""
        self.write({"state": "disputed"})

    def action_view_dip_readings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dip Readings"),
            "res_model": "fms.tank.dip.reading",
            "view_mode": "list,form",
            "domain": [("shift_id", "=", self.id)],
            "context": {"default_shift_id": self.id},
        }

    def action_view_meter_readings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Meter Readings"),
            "res_model": "fms.meter.reading",
            "view_mode": "list,form",
            "domain": [("shift_id", "=", self.id)],
            "context": {"default_shift_id": self.id},
        }

    # ── Constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "shift_date_label_company_uniq",
            "unique(company_id, shift_date, shift_label)",
            "A shift for this company, date, and label already exists.",
        ),
    ]

    @api.constrains("state", "company_id")
    def _check_one_open_shift_per_company(self):
        for rec in self:
            if rec.state != "open":
                continue
            others = self.search([
                ("company_id", "=", rec.company_id.id),
                ("state", "=", "open"),
                ("id", "!=", rec.id),
            ])
            if others:
                raise ValidationError(
                    _(
                        "Company '%(co)s' already has an open shift: "
                        "'%(other)s'.  Close or cancel it before opening another.",
                        co=rec.company_id.name,
                        other=others[0].name,
                    )
                )
