from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FmsPumpNozzle(models.Model):
    """A dispensing nozzle on a pump, plumbed to one underground fuel tank.

    Hierarchy: Island → Pump → Nozzle → Tank
    """

    _name = "fms.pump.nozzle"
    _description = "Pump Nozzle"
    _order = "pump_id, nozzle_number"
    _rec_name = "display_name"

    pump_id = fields.Many2one(
        "fms.pump",
        string="Pump",
        required=True,
        ondelete="cascade",
        index=True,
    )
    nozzle_number = fields.Integer(
        string="Nozzle #",
        required=True,
        default=1,
        help="Sequential nozzle position on this pump (1-based).  Unique per pump.",
    )
    tank_location_id = fields.Many2one(
        "stock.location",
        string="Tank",
        required=True,
        domain="[('fms_is_fuel_tank', '=', True)]",
        ondelete="restrict",
        help="The underground fuel tank this nozzle draws from.",
    )
    active = fields.Boolean(default=True)

    # Convenience: derived from the tank's linked product
    fuel_product_id = fields.Many2one(
        "product.product",
        string="Fuel Grade",
        related="tank_location_id.fms_fuel_product_id",
        store=False,
        help="Fuel grade dispensed — derived from the assigned tank.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="pump_id.company_id",
        store=True,
        index=True,
        help="Inherited from the pump's company.",
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=False,
    )

    _sql_constraints = [
        (
            "nozzle_number_pump_uniq",
            "unique(pump_id, nozzle_number)",
            "Nozzle number must be unique within a pump.",
        ),
    ]

    def _compute_display_name(self):
        for rec in self:
            if rec.pump_id and rec.nozzle_number:
                rec.display_name = f"{rec.pump_id.name} / Nozzle {rec.nozzle_number}"
            else:
                rec.display_name = "New Nozzle"

    @api.constrains("tank_location_id")
    def _check_tank_is_fuel_tank(self):
        for rec in self:
            if rec.tank_location_id and not rec.tank_location_id.fms_is_fuel_tank:
                raise ValidationError(
                    _(
                        "Location '%(loc)s' cannot be assigned to nozzle %(nozzle)s "
                        "of pump '%(pump)s': it is not marked as a Fuel Tank.",
                        loc=rec.tank_location_id.complete_name,
                        nozzle=rec.nozzle_number,
                        pump=rec.pump_id.name,
                    )
                )

    @api.constrains("tank_location_id", "pump_id")
    def _check_tank_company_matches_pump(self):
        for rec in self:
            tank_company = rec.tank_location_id.company_id
            pump_company = rec.pump_id.company_id
            # Only enforce when both have a company set (some locations are shared)
            if tank_company and pump_company and tank_company != pump_company:
                raise ValidationError(
                    _(
                        "Tank '%(tank)s' belongs to company '%(tank_co)s' but "
                        "pump '%(pump)s' belongs to company '%(pump_co)s'. "
                        "Nozzles must draw from a tank in the same company.",
                        tank=rec.tank_location_id.complete_name,
                        tank_co=tank_company.name,
                        pump=rec.pump_id.name,
                        pump_co=pump_company.name,
                    )
                )
