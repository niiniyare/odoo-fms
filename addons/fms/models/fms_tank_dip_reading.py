from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .fms_calibration_interpolation import (
    CalibrationInterpolationError,
    interpolate_volume,
)


class FmsTankDipReading(models.Model):
    """Manual dip reading for one fuel tank at the start or end of a shift.

    The dip height is measured physically with a calibrated dip stick.
    On confirmation the active calibration chart is used to convert the
    measured height into an observed volume via linear interpolation.

    Confirmed readings are immutable.
    """

    _name = "fms.tank.dip.reading"
    _description = "Tank Dip Reading"
    _order = "shift_id desc, reading_type, tank_location_id"
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

    # ── Tank ──────────────────────────────────────────────────────────────

    tank_location_id = fields.Many2one(
        "stock.location",
        string="Tank",
        required=True,
        ondelete="restrict",
        domain="[('fms_is_fuel_tank', '=', True), ('active', '=', True)]",
        help="The fuel tank being dipped.",
    )
    fuel_product_id = fields.Many2one(
        "product.product",
        string="Fuel Product",
        related="tank_location_id.fms_fuel_product_id",
        store=True,
        help="Fuel grade in this tank — derived from the tank configuration.",
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
    )
    dip_height_mm = fields.Float(
        string="Dip Height (mm)",
        required=True,
        digits=(10, 1),
        help="Physical dip stick measurement in millimetres.",
    )
    observed_volume_litres = fields.Float(
        string="Observed Volume (L)",
        digits=(16, 3),
        readonly=True,
        copy=False,
        help="Volume derived from the dip height via the active calibration "
             "chart.  Calculated and stored on confirmation.",
    )
    water_height_mm = fields.Float(
        string="Water Height (mm)",
        digits=(10, 1),
        default=0.0,
        help="Water ingress measured at the bottom of the dip stick (mm).  "
             "Values above 20 mm trigger an alert.",
    )
    temperature_celsius = fields.Float(
        string="Temperature (°C)",
        digits=(5, 1),
        help="Fuel temperature at time of dipping (optional, for correction "
             "calculations in future milestones).",
    )

    # ── Audit ─────────────────────────────────────────────────────────────

    reading_time = fields.Datetime(
        string="Reading Time",
        required=True,
        default=fields.Datetime.now,
    )
    recorded_by = fields.Many2one(
        "res.users",
        string="Recorded By",
        default=lambda self: self.env.uid,
    )

    # ── State ─────────────────────────────────────────────────────────────

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
            if rec.tank_location_id:
                parts.append(rec.tank_location_id.name)
            parts.append(type_label.get(rec.reading_type, ""))
            rec.display_name = " / ".join(parts) if parts else _("New Dip Reading")

    # ── ORM overrides ─────────────────────────────────────────────────────

    def write(self, vals):
        if "state" not in vals or vals.get("state") == "confirmed":
            for rec in self:
                if rec.state == "confirmed":
                    raise UserError(
                        _(
                            "Dip reading '%(name)s' is confirmed and cannot be "
                            "modified.  Contact your supervisor to correct it.",
                            name=rec.display_name,
                        )
                    )
        return super().write(vals)

    # ── Calibration helper ────────────────────────────────────────────────

    def _get_active_calibration_chart(self):
        """Return the single active calibration chart for self.tank_location_id.

        Raises ValidationError if none exists.
        """
        self.ensure_one()
        chart = self.env["fms.tank.calibration.chart"].search([
            ("tank_location_id", "=", self.tank_location_id.id),
            ("active", "=", True),
        ], limit=1)
        if not chart:
            raise ValidationError(
                _(
                    "No active calibration chart found for tank '%(tank)s'.  "
                    "Create and activate a calibration chart before recording "
                    "dip readings.",
                    tank=self.tank_location_id.display_name,
                )
            )
        return chart

    def _compute_volume_from_dip(self, dip_height_mm: float) -> float:
        """Interpolate observed volume for dip_height_mm using the active chart."""
        self.ensure_one()
        chart = self._get_active_calibration_chart()
        lines = [(l.dip_height_mm, l.volume_litres) for l in chart.line_ids]
        try:
            return interpolate_volume(dip_height_mm, lines)
        except CalibrationInterpolationError as e:
            raise ValidationError(
                _(
                    "Calibration interpolation failed for tank '%(tank)s': %(err)s",
                    tank=self.tank_location_id.display_name,
                    err=str(e),
                )
            ) from e

    # ── Transition action ─────────────────────────────────────────────────

    def action_confirm(self):
        """Draft → Confirmed.  Interpolates volume, stamps confirmed_at, locks."""
        for rec in self:
            if rec.state == "confirmed":
                continue
            volume = rec._compute_volume_from_dip(rec.dip_height_mm)
            super(FmsTankDipReading, rec).write({
                "state":                  "confirmed",
                "observed_volume_litres": volume,
                "confirmed_at":           fields.Datetime.now(),
            })
            # Post water-ingress alert to shift chatter when water > 20 mm
            if rec.water_height_mm > 20.0:
                rec.shift_id.message_post(
                    body=_(
                        "⚠️ Water ingress alert on tank '%(tank)s' "
                        "(%(type)s dip, shift %(shift)s): "
                        "water height %(h).1f mm exceeds the 20 mm threshold.",
                        tank=rec.tank_location_id.name,
                        type=rec.reading_type,
                        shift=rec.shift_id.name,
                        h=rec.water_height_mm,
                    )
                )

    # ── SQL constraints ───────────────────────────────────────────────────

    _sql_constraints = [
        (
            "one_dip_type_per_tank_per_shift",
            "unique(shift_id, tank_location_id, reading_type)",
            "Only one dip reading of each type (opening/closing) is allowed "
            "per tank per shift.",
        ),
    ]

    # ── ORM constraints ───────────────────────────────────────────────────

    @api.constrains("dip_height_mm")
    def _check_dip_height_non_negative(self):
        for rec in self:
            if rec.dip_height_mm < 0:
                raise ValidationError(
                    _(
                        "Dip height %(h).1f mm on reading '%(name)s' cannot be "
                        "negative.",
                        h=rec.dip_height_mm,
                        name=rec.display_name,
                    )
                )

    @api.constrains("water_height_mm")
    def _check_water_height_non_negative(self):
        for rec in self:
            if rec.water_height_mm < 0:
                raise ValidationError(
                    _(
                        "Water height %(h).1f mm on reading '%(name)s' cannot be "
                        "negative.",
                        h=rec.water_height_mm,
                        name=rec.display_name,
                    )
                )

    @api.constrains("tank_location_id")
    def _check_tank_is_active_fuel_tank(self):
        for rec in self:
            tank = rec.tank_location_id
            if not tank.fms_is_fuel_tank:
                raise ValidationError(
                    _(
                        "Location '%(loc)s' is not an FMS fuel tank.",
                        loc=tank.display_name,
                    )
                )
            if not tank.active:
                raise ValidationError(
                    _(
                        "Tank '%(tank)s' is archived and cannot receive dip readings.",
                        tank=tank.display_name,
                    )
                )

    @api.constrains("shift_id", "reading_type")
    def _check_shift_state_matches_reading_type(self):
        for rec in self:
            state = rec.shift_id.state
            if rec.reading_type == "opening":
                if state in ("closed", "disputed"):
                    raise ValidationError(
                        _(
                            "Cannot add an opening dip to shift '%(shift)s' — "
                            "it is in state '%(state)s'.",
                            shift=rec.shift_id.name,
                            state=state,
                        )
                    )
            elif rec.reading_type == "closing":
                if state != "closing":
                    raise ValidationError(
                        _(
                            "Closing dip readings can only be recorded while the "
                            "shift is in the 'Closing' state.  Shift '%(shift)s' "
                            "is currently '%(state)s'.",
                            shift=rec.shift_id.name,
                            state=state,
                        )
                    )
