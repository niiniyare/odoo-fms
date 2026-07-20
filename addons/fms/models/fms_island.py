from odoo import fields, models


class FmsIsland(models.Model):
    """A physical island on the forecourt — a concrete divider grouping pump units.

    Islands are the top-level physical grouping:
        Island → Pump → Nozzle → Tank
    """

    _name = "fms.island"
    _description = "Forecourt Island"
    _order = "name"

    name = fields.Char(
        string="Island Name",
        required=True,
        help="Physical label for this island (e.g. 'Island 3').",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Station (company) that owns this island.",
    )
    active = fields.Boolean(default=True)
    pump_ids = fields.One2many(
        "fms.pump",
        "island_id",
        string="Pumps",
    )
    pump_count = fields.Integer(
        string="Pumps",
        compute="_compute_pump_count",
    )

    def _compute_pump_count(self):
        for rec in self:
            rec.pump_count = len(rec.pump_ids)
