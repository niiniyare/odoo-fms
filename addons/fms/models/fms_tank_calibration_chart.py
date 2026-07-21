from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FmsTankCalibrationChart(models.Model):
    """Certified strapping table (dip height → volume) for one fuel tank.

    A calibration chart is issued by a licensed calibrator (EPRA-registered in
    Kenya) and must be updated whenever a tank is physically altered.  Only one
    chart per tank may be active at a time; archive the old one before activating
    a replacement.
    """

    _name = "fms.tank.calibration.chart"
    _description = "Tank Calibration Chart"
    _order = "tank_location_id, calibration_date desc"
    _rec_name = "name"

    name = fields.Char(
        string="Chart Name",
        required=True,
        help="Short label for this calibration chart, e.g. 'Tank 2 – UNL 2025'.",
    )
    tank_location_id = fields.Many2one(
        "stock.location",
        string="Tank",
        required=True,
        ondelete="restrict",
        domain="[('fms_is_fuel_tank', '=', True)]",
        help="The fuel tank this chart applies to.",
    )
    certificate_number = fields.Char(
        string="Certificate Number",
        help="Official calibration certificate reference issued by the calibrator.",
    )
    calibration_date = fields.Date(
        string="Calibration Date",
        required=True,
        help="Date on which the physical calibration was performed.",
    )
    capacity_litres = fields.Float(
        string="Certified Capacity (L)",
        digits=(16, 3),
        help="Total tank capacity as certified by the calibrator (litres at 100% dip).",
    )
    active = fields.Boolean(
        default=True,
        help="Only one active chart per tank is allowed.  Archive to deactivate.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="tank_location_id.company_id",
        store=True,
        index=True,
    )
    line_ids = fields.One2many(
        "fms.tank.calibration.chart.line",
        "calibration_chart_id",
        string="Calibration Lines",
    )
    line_count = fields.Integer(
        string="Lines",
        compute="_compute_line_count",
    )

    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    # ── Constraints ────────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "active_chart_per_tank_uniq",
            # Partial unique index: only one active=True chart per tank.
            # PostgreSQL supports this via a partial index; Odoo's _sql_constraints
            # syntax maps directly to CREATE UNIQUE INDEX when the constraint
            # expression is a WHERE clause — but that requires manual SQL.
            # We enforce this via @api.constrains instead (see below).
            # Placeholder constraint to satisfy the list requirement:
            "CHECK(1=1)",
            "",
        ),
    ]

    @api.constrains("tank_location_id", "active")
    def _check_one_active_chart_per_tank(self):
        for rec in self:
            if not rec.active:
                continue
            duplicates = self.search([
                ("tank_location_id", "=", rec.tank_location_id.id),
                ("active", "=", True),
                ("id", "!=", rec.id),
            ])
            if duplicates:
                raise ValidationError(
                    _(
                        "Tank '%(tank)s' already has an active calibration chart "
                        "('%(chart)s').  Archive the existing chart before "
                        "activating a new one.",
                        tank=rec.tank_location_id.display_name,
                        chart=duplicates[0].name,
                    )
                )

    @api.constrains("tank_location_id")
    def _check_tank_is_fuel_tank(self):
        for rec in self:
            if rec.tank_location_id and not rec.tank_location_id.fms_is_fuel_tank:
                raise ValidationError(
                    _(
                        "Location '%(loc)s' is not a fuel tank.  Calibration "
                        "charts can only be assigned to FMS fuel tank locations.",
                        loc=rec.tank_location_id.display_name,
                    )
                )


class FmsTankCalibrationChartLine(models.Model):
    """One row in a strapping table: a measured dip height mapped to a volume.

    Lines must be unique by dip height within a chart and are ordered by
    dip_height_mm ascending.  Interpolation between rows is deferred to a later
    task (fms.tank.dip.reading).
    """

    _name = "fms.tank.calibration.chart.line"
    _description = "Calibration Chart Line"
    _order = "calibration_chart_id, dip_height_mm"

    calibration_chart_id = fields.Many2one(
        "fms.tank.calibration.chart",
        string="Calibration Chart",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Used to manually reorder lines before sorting by dip height.",
    )
    dip_height_mm = fields.Float(
        string="Dip Height (mm)",
        required=True,
        digits=(10, 1),
        help="Measured dip height in millimetres.",
    )
    volume_litres = fields.Float(
        string="Volume (L)",
        required=True,
        digits=(16, 3),
        help="Corresponding fuel volume in litres at this dip height.",
    )

    # ── Constraints ────────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "dip_height_chart_uniq",
            "unique(calibration_chart_id, dip_height_mm)",
            "Dip height must be unique within a calibration chart.",
        ),
    ]

    @api.constrains("dip_height_mm")
    def _check_dip_height_positive(self):
        for rec in self:
            if rec.dip_height_mm < 0:
                raise ValidationError(
                    _(
                        "Dip height %(h)s mm is invalid — dip heights must be "
                        "zero or positive.",
                        h=rec.dip_height_mm,
                    )
                )

    @api.constrains("volume_litres")
    def _check_volume_non_negative(self):
        for rec in self:
            if rec.volume_litres < 0:
                raise ValidationError(
                    _(
                        "Volume %(v)s L is invalid — volumes must be "
                        "non-negative.",
                        v=rec.volume_litres,
                    )
                )
