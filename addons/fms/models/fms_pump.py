from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FmsPump(models.Model):
    """A physical pump unit on a forecourt island.

    Hierarchy: Island → Pump → Nozzle → Tank
    """

    _name = "fms.pump"
    _description = "Forecourt Pump"
    _order = "name"

    name = fields.Char(
        string="Pump Name",
        required=True,
        help="Physical pump identifier (e.g. 'U5', 'L7').  Unique per company.",
    )
    island_id = fields.Many2one(
        "fms.island",
        string="Island",
        required=True,
        ondelete="restrict",
        help="The forecourt island this pump belongs to.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        related="island_id.company_id",
        store=True,
        help="Inherited from the island's company.",
    )
    active = fields.Boolean(default=True)
    nozzle_ids = fields.One2many(
        "fms.pump.nozzle",
        "pump_id",
        string="Nozzles",
    )

    _sql_constraints = [
        (
            "pump_name_company_uniq",
            "unique(name, company_id)",
            "Pump name must be unique per company.",
        ),
    ]

    @api.constrains("island_id", "company_id")
    def _check_company_matches_island(self):
        for rec in self:
            if rec.island_id and rec.company_id != rec.island_id.company_id:
                raise ValidationError(
                    _(
                        "Pump '%(pump)s' company (%(pump_co)s) does not match "
                        "Island '%(island)s' company (%(island_co)s).",
                        pump=rec.name,
                        pump_co=rec.company_id.name,
                        island=rec.island_id.name,
                        island_co=rec.island_id.company_id.name,
                    )
                )
