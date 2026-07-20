from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FmsSitePreferences(models.Model):
    """Per-station configuration for variance thresholds and operational settings.

    Exactly one record per company is allowed.  Account-name overrides are
    deferred to Task 8.1 when the journal-posting logic needs them.
    """

    _name = "fms.site.preferences"
    _description = "Forecourt Site Preferences"
    _rec_name = "company_id"

    # ── Identity ──────────────────────────────────────────────────────────────

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Station / company this preferences record belongs to.",
    )

    # ── Meter validation thresholds (§4.2–4.3) ───────────────────────────────

    meter_check_a_warn_kes = fields.Float(
        string="Check A — Warning Threshold (KES)",
        default=5.0,
        digits=(16, 2),
        help=(
            "Electronic Cash vs. (Elec Vol × Rate) discrepancy at which a "
            "Warning is raised.  Pass < this value; Warning ≤ 20; Fail > 20."
        ),
    )
    meter_check_b_warn_pct = fields.Float(
        string="Check B — Warning Threshold (%)",
        default=0.30,
        digits=(5, 2),
        help="Elec Vol vs. Mech Vol divergence percentage that triggers a Warning.",
    )
    meter_check_b_fail_pct = fields.Float(
        string="Check B — Fail Threshold (%)",
        default=0.50,
        digits=(5, 2),
        help="Divergence percentage that triggers a Fail (blocks shift close).",
    )
    meter_check_b_tamper_pct = fields.Float(
        string="Check B — Tamper/Auto-Lock Threshold (%)",
        default=1.00,
        digits=(5, 2),
        help=(
            "Divergence percentage that triggers Critical: pump is automatically "
            "locked (fms.pump.is_active → False) until inspected."
        ),
    )

    # ── Wetstock variance thresholds (§13) ────────────────────────────────────

    wetstock_normal_pct = fields.Float(
        string="Wetstock Normal Threshold (%)",
        default=0.30,
        digits=(5, 2),
        help="Variance ≤ this value is classified Normal.",
    )
    wetstock_elevated_pct = fields.Float(
        string="Wetstock Elevated Threshold (%)",
        default=0.50,
        digits=(5, 2),
        help="Variance between Normal and this value is Elevated; above is Critical.",
    )

    # ── Cash variance thresholds (§11.3) ─────────────────────────────────────

    cash_normal_kes = fields.Float(
        string="Cash Normal Threshold (KES)",
        default=50.0,
        digits=(16, 2),
        help="Per-cashier cash over/(under) ≤ this value is classified Normal.",
    )
    cash_elevated_kes = fields.Float(
        string="Cash Elevated Threshold (KES)",
        default=200.0,
        digits=(16, 2),
        help="Cash variance between Normal and this value is Elevated; above is Critical.",
    )
    cash_pickup_threshold = fields.Float(
        string="Cash Pickup Trigger (KES)",
        default=30000.0,
        digits=(16, 2),
        help="Till balance above which supervisor triggers a cash pickup.",
    )

    # ── Operational settings ──────────────────────────────────────────────────

    min_settle_minutes = fields.Integer(
        string="Minimum Post-Delivery Settle Time (min)",
        default=10,
        help="Minutes to wait after offload completes before taking the after-dip.",
    )
    send_daily_summary = fields.Boolean(
        string="Send Daily Shift Summary Email",
        default=True,
    )
    report_recipient_ids = fields.Many2many(
        "res.partner",
        string="Report Recipients",
        help="Partners who receive the automated daily shift summary email.",
    )

    # ── SQL uniqueness constraint ─────────────────────────────────────────────

    _sql_constraints = [
        (
            "company_uniq",
            "unique(company_id)",
            "Only one Site Preferences record may exist per company.",
        ),
    ]

    # ── ORM-level duplicate guard (provides a readable error before the DB hit) ──

    @api.constrains("company_id")
    def _check_company_unique(self):
        for rec in self:
            duplicate = self.search(
                [("company_id", "=", rec.company_id.id), ("id", "!=", rec.id)],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "A Site Preferences record already exists for %(company)s. "
                        "Only one record is allowed per company.",
                        company=rec.company_id.name,
                    )
                )

    # ── Threshold sanity checks ───────────────────────────────────────────────

    @api.constrains(
        "meter_check_b_warn_pct",
        "meter_check_b_fail_pct",
        "meter_check_b_tamper_pct",
    )
    def _check_check_b_order(self):
        for rec in self:
            if not (
                0 < rec.meter_check_b_warn_pct
                < rec.meter_check_b_fail_pct
                < rec.meter_check_b_tamper_pct
            ):
                raise ValidationError(
                    _(
                        "Check B thresholds must satisfy: "
                        "Warning < Fail < Tamper (all > 0). "
                        "Current values: %(warn)s%% < %(fail)s%% < %(tamper)s%%",
                        warn=rec.meter_check_b_warn_pct,
                        fail=rec.meter_check_b_fail_pct,
                        tamper=rec.meter_check_b_tamper_pct,
                    )
                )

    @api.constrains("wetstock_normal_pct", "wetstock_elevated_pct")
    def _check_wetstock_order(self):
        for rec in self:
            if not (0 < rec.wetstock_normal_pct < rec.wetstock_elevated_pct):
                raise ValidationError(
                    _(
                        "Wetstock thresholds must satisfy: Normal < Elevated (both > 0). "
                        "Current values: %(normal)s%% < %(elevated)s%%",
                        normal=rec.wetstock_normal_pct,
                        elevated=rec.wetstock_elevated_pct,
                    )
                )

    @api.constrains("cash_normal_kes", "cash_elevated_kes")
    def _check_cash_order(self):
        for rec in self:
            if not (0 < rec.cash_normal_kes < rec.cash_elevated_kes):
                raise ValidationError(
                    _(
                        "Cash thresholds must satisfy: Normal < Elevated (both > 0). "
                        "Current values: KES %(normal)s < KES %(elevated)s",
                        normal=rec.cash_normal_kes,
                        elevated=rec.cash_elevated_kes,
                    )
                )
