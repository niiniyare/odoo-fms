from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FmsMeterReading(models.Model):
    """Totalizer reading taken from a pump nozzle at the start or end of a shift.

    Opening reading  — baseline captured when the shift begins.
    Closing reading  — captured when the shift moves to 'closing' state.
    dispensed_litres — closing minus opening; only populated once both sides
                       are confirmed.

    Once confirmed the record is fully locked (write() override).
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
    fuel_product_id = fields.Many2one(
        "product.product",
        string="Fuel Product",
        related="nozzle_id.fuel_product_id",
        store=True,
        help="Fuel grade dispensed — derived from the nozzle's tank.",
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
             "increases (or restarts from 0 on meter replacement).",
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

    # ── Dispensed volume (populated on closing readings once confirmed) ────

    opening_totalizer_litres = fields.Float(
        string="Opening Totalizer (L)",
        digits=(16, 3),
        readonly=True,
        copy=False,
        help="Confirmed opening totalizer for this nozzle in this shift.  "
             "Populated automatically when a closing reading is confirmed.",
    )
    dispensed_litres = fields.Float(
        string="Dispensed (L)",
        digits=(16, 3),
        readonly=True,
        copy=False,
        help="Litres dispensed this shift = closing totalizer − opening totalizer.  "
             "Calculated and stored when the closing reading is confirmed.",
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
        # Lock confirmed readings.  action_confirm() bypasses this by calling
        # super().write() directly.
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
        """Draft → Confirmed.

        For closing readings:
          • Verifies a confirmed opening reading exists for this nozzle/shift.
          • Verifies closing totalizer ≥ opening totalizer.
          • Stores opening_totalizer_litres and dispensed_litres.
        Stamps confirmed_at and locks the record for all reading types.
        """
        for rec in self:
            if rec.state == "confirmed":
                continue

            update_vals = {
                "state":        "confirmed",
                "confirmed_at": fields.Datetime.now(),
            }

            if rec.reading_type == "closing":
                opening = self.search([
                    ("shift_id",     "=", rec.shift_id.id),
                    ("nozzle_id",    "=", rec.nozzle_id.id),
                    ("reading_type", "=", "opening"),
                    ("state",        "=", "confirmed"),
                ], limit=1)

                if not opening:
                    raise ValidationError(
                        _(
                            "Cannot confirm closing reading for nozzle %(nozzle)s "
                            "on shift '%(shift)s': no confirmed opening reading "
                            "exists for this nozzle.",
                            nozzle=f"{rec.nozzle_id.pump_id.name}/N{rec.nozzle_id.nozzle_number}",
                            shift=rec.shift_id.name,
                        )
                    )

                dispensed = rec.totalizer_litres - opening.totalizer_litres
                if dispensed < 0:
                    raise ValidationError(
                        _(
                            "Closing totalizer %(close).3f L is less than the "
                            "opening totalizer %(open).3f L for nozzle %(nozzle)s "
                            "on shift '%(shift)s'.  Dispensed litres cannot be "
                            "negative.",
                            close=rec.totalizer_litres,
                            open=opening.totalizer_litres,
                            nozzle=f"{rec.nozzle_id.pump_id.name}/N{rec.nozzle_id.nozzle_number}",
                            shift=rec.shift_id.name,
                        )
                    )

                update_vals["opening_totalizer_litres"] = opening.totalizer_litres
                update_vals["dispensed_litres"] = dispensed

            # Bypass the lock guard — we are the one setting confirmed state
            super(FmsMeterReading, rec).write(update_vals)

    # ── SQL constraints ───────────────────────────────────────────────────

    _sql_constraints = [
        (
            "one_reading_type_per_nozzle_per_shift",
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

    @api.constrains("shift_id", "reading_type")
    def _check_shift_state_matches_reading_type(self):
        """Opening readings require an active shift; closing require 'closing' state."""
        for rec in self:
            state = rec.shift_id.state
            if rec.reading_type == "opening":
                if state in ("closed", "disputed"):
                    raise ValidationError(
                        _(
                            "Cannot add an opening reading to shift '%(shift)s' — "
                            "it is in state '%(state)s'.",
                            shift=rec.shift_id.name,
                            state=state,
                        )
                    )
            elif rec.reading_type == "closing":
                if state != "closing":
                    raise ValidationError(
                        _(
                            "Closing readings can only be recorded while the shift "
                            "is in the 'Closing' state.  Shift '%(shift)s' is "
                            "currently '%(state)s'.",
                            shift=rec.shift_id.name,
                            state=state,
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
