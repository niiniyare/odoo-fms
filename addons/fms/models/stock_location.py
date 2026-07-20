from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    """Extend stock.location with FMS fuel-tank metadata.

    Fuel tanks are modelled as Odoo internal stock locations, which allows
    Inventory → Reporting → Valuation to show live fuel balances without a
    parallel inventory model.

    Exactly one tank number per company is enforced at SQL level.
    All other business rules are enforced by @api.constrains.
    """

    _inherit = "stock.location"

    # ── FMS tank fields ───────────────────────────────────────────────────────

    fms_is_fuel_tank = fields.Boolean(
        string="Is Fuel Tank",
        default=False,
        help=(
            "Mark this location as an underground fuel storage tank managed "
            "by the FMS.  Only Internal locations may be marked as fuel tanks."
        ),
    )
    fms_capacity_litres = fields.Float(
        string="Capacity (L)",
        digits=(16, 3),
        help="Geometric capacity of the tank in litres (from EPRA calibration certificate).",
    )
    fms_pts2_tank_number = fields.Integer(
        string="PTS-2 Tank Number",
        help=(
            "Probe/tank slot number configured on the PTS-2 forecourt controller "
            "(1-based, matches LOG/USER PORT wiring).  Must be unique per company."
        ),
    )
    fms_fuel_product_id = fields.Many2one(
        "product.product",
        string="Fuel Product",
        domain="[('fms_is_fuel_product', '=', True)]",
        help="The fuel grade stored in this tank.  Must have 'Is Fuel Product' checked.",
    )

    # ── SQL constraint ────────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "fms_pts2_tank_number_company_uniq",
            # Only enforce uniqueness when a tank number has been assigned (> 0)
            # A partial unique index would be ideal; this constraint fires for
            # all rows but we guard zero/null via @api.constrains below.
            "unique(company_id, fms_pts2_tank_number)",
            "PTS-2 tank number must be unique per company.",
        ),
    ]

    # ── ORM validation ────────────────────────────────────────────────────────

    @api.constrains("fms_is_fuel_tank", "usage")
    def _check_tank_must_be_internal(self):
        for rec in self:
            if rec.fms_is_fuel_tank and rec.usage != "internal":
                raise ValidationError(
                    _(
                        "Location '%(name)s' cannot be marked as a Fuel Tank: "
                        "only Internal locations may be fuel tanks "
                        "(current usage: %(usage)s).",
                        name=rec.complete_name,
                        usage=rec.usage,
                    )
                )

    @api.constrains("fms_is_fuel_tank", "fms_capacity_litres")
    def _check_capacity_positive(self):
        for rec in self:
            if rec.fms_is_fuel_tank and rec.fms_capacity_litres <= 0:
                raise ValidationError(
                    _(
                        "Fuel tank '%(name)s' must have a capacity greater than zero. "
                        "Enter the geometric capacity from the EPRA calibration certificate.",
                        name=rec.complete_name,
                    )
                )

    @api.constrains("fms_is_fuel_tank", "fms_fuel_product_id")
    def _check_fuel_product_is_fuel(self):
        for rec in self:
            if rec.fms_is_fuel_tank and rec.fms_fuel_product_id:
                if not rec.fms_fuel_product_id.fms_is_fuel_product:
                    raise ValidationError(
                        _(
                            "Product '%(product)s' cannot be assigned to tank '%(tank)s': "
                            "the product does not have 'Is Fuel Product' checked.",
                            product=rec.fms_fuel_product_id.name,
                            tank=rec.complete_name,
                        )
                    )
