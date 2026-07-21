from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FmsMeterReading(models.Model):
    """Totalizer reading taken from a pump nozzle at the start or end of a shift.

    The opening reading is the baseline from which fuel sold during the shift
    is calculated.  Once confirmed the record is locked — all edits are rejected
    by the write() override.

    Closing readings (reading_type='closing') are recorded in a later task;
    the model supports them structurally so no migration is required then.
    """

    _name = "fms.meter.reading"
    _description = "Meter Reading"
    _order = "shift_id desc, reading_type, nozzle_id"
    _rec_name = "display_name"

    # ── Identity ──────────────────────────────────────────────────────────

    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
    )
    shift_id = fields.Many2one(
        "fms.shift",
        string="Shift",
        required=True,
        ondelete="restrict",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="shift_id.company_id",
        store=True,
        index=True,
    )

    # ── Equipment ─────────────────────────────────────────────────────────

    nozzle_id = fields.Many2one(
        "fms.pump.nozzle",
        string="Nozzle",
        required=True,
        ondelete="restrict",
        domain="[('active', '=', True)]",
        help="The nozzle whose totalizer counter is being recorded.",
    )
    pump_id = fields.Many2one(
        "fms.pump",
        string="Pump",
        related="nozzle_id.pump_id",
        store=True,
        index=True,
        help="Derived from the selected nozzle.",
    )
    tank_location_id = fields.Many2one(
        "stock.location",
        string="Tank",
        related="nozzle_id.tank_location_id",
        store=True,
        help="Fuel tank this nozzle draws from — derived from the nozzle.",
    )

    # ── Reading ───────────────────────────────────────────────────────────

    reading_type = fields.Selection(
        [
            ("opening", "Opening"),
            ("closing", "Closing"),
        ],
        string="Reading Type",
        required=True,
        default="opening",
        index=True,
        help="Opening readings are captured at shift start; "
             "closing readings at shift end.",
    )
    totalizer_litres = fields.Float(
        string="Totalizer (L)",
        required=True,
        digits=(16, 3),
        help="Cumulative lifetime totalizer counter on the pump's electronic meter "
             "at the time of reading (litres).  This counter never resets — it only "
             "increases or (on meter replacement) restarts from 0.",
    )
    reading_time = fields.Datetime(
        string="Reading Time",
        required=True,
        default=fields.Datetime.now,
        help="Timestamp when the totalizer value was physically observed.",
    )
    recorded_by = fields.Many2one(
        "res.users",
        string="Recorded By",
        default=lambda self: self.env.uid,
        help="User who entered this reading.",
    )

    # ── Status ────────────────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft",     "Draft"),
            ("confirmed", "Confirmed"),
        ],
        string="State",
        default="draft",
        required=True,
        index=True,
        copy=False,
    )
    confirmed_at = fields.Datetime(
        string="Confirmed At",
        readonly=True,
        copy=False,
    )

    # ── Computed ──────────────────────────────────────────────────────────

    def _compute_display_name(self):
        type_label = dict(self._fields["reading_type"].selection)
        for rec in self:
            parts = []
            if rec.shift_id:
                parts.append(rec.shift_id.name)
            if rec.nozzle_id:
                parts.append(rec.nozzle_id.pump_id.name if rec.nozzle_id.pump_id else "?")
                parts.append(f"N{rec.nozzle_id.nozzle_number}")
            parts.append(type_label.get(rec.reading_type, ""))
            rec.display_name = " / ".join(parts) if parts else _("New Reading")

    # ── ORM overrides ─────────────────────────────────────────────────────

    def write(self, vals):
        # Lock confirmed readings — no field may be changed except state
        # transitions driven by action_confirm() itself.
        if "state" not in vals or vals.get("state") == "confirmed":
            for rec in self:
                if rec.state == "confirmed":
                    raise UserError(
                        _(
                            "Meter reading '%(name)s' is confirmed and cannot be "
                            "modified.  To correct it, contact your supervisor.",
                            name=rec.display_name,
                        )
                    )
        return super().write(vals)

    # ── Transition action ─────────────────────────────────────────────────

    def action_confirm(self):
        """Draft → Confirmed.  Stamps confirmed_at and locks the record."""
        for rec in self:
            if rec.state == "confirmed":
                continue
            # Call super().write() directly to bypass our own lock guard above
            super(FmsMeterReading, rec).write({
                "state":        "confirmed",
                "confirmed_at": fields.Datetime.now(),
            })

    # ── SQL constraints ───────────────────────────────────────────────────

    _sql_constraints = [
        (
            "one_opening_per_nozzle_per_shift",
            "unique(shift_id, nozzle_id, reading_type)",
            "Only one reading of each type (opening/closing) is allowed per "
            "nozzle per shift.",
        ),
    ]

    # ── ORM constraints ───────────────────────────────────────────────────

    @api.constrains("totalizer_litres")
    def _check_totalizer_non_negative(self):
        for rec in self:
            if rec.totalizer_litres < 0:
                raise ValidationError(
                    _(
                        "Totalizer value %(v).3f L on reading '%(name)s' is "
                        "invalid — totalizer counters cannot be negative.",
                        v=rec.totalizer_litres,
                        name=rec.display_name,
                    )
                )

    @api.constrains("shift_id")
    def _check_shift_active(self):
        """Reading must belong to a shift that has not been closed or disputed."""
        blocked = {"closed", "disputed"}
        for rec in self:
            if rec.shift_id.state in blocked:
                raise ValidationError(
                    _(
                        "Cannot add a meter reading to shift '%(shift)s' — "
                        "it is in state '%(state)s'.",
                        shift=rec.shift_id.name,
                        state=rec.shift_id.state,
                    )
                )

    @api.constrains("nozzle_id")
    def _check_nozzle_active(self):
        for rec in self:
            if rec.nozzle_id and not rec.nozzle_id.active:
                raise ValidationError(
                    _(
                        "Nozzle %(n)s on pump '%(pump)s' is inactive and cannot "
                        "receive a meter reading.",
                        n=rec.nozzle_id.nozzle_number,
                        pump=rec.nozzle_id.pump_id.name,
                    )
                )
