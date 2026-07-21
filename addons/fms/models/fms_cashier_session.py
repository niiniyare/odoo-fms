from odoo import fields, models


class FmsCashierSession(models.Model):
    """Cashier session — links one cashier to one shift.

    Stub model created in Task 2.1 to satisfy the fms.shift.cashier_session_ids
    One2many.  Full implementation is in Task 5.1 (Milestone 5).
    """

    _name = "fms.cashier.session"
    _description = "Cashier Session"
    _order = "shift_id, id"

    shift_id = fields.Many2one(
        "fms.shift",
        string="Shift",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="shift_id.company_id",
        store=True,
        index=True,
    )
