from odoo import fields, models


class ProductTemplate(models.Model):
    """Extend product.template with FMS fuel-grade classification fields.

    These two fields are used throughout the FMS: to filter valid products
    in meter readings, to determine which wetstock tank a nozzle feeds, and
    to drive the journal entry account selection at shift close.
    """

    _inherit = "product.template"

    fms_is_fuel_product = fields.Boolean(
        string="Is Fuel Product",
        default=False,
        help="Mark this product as a dispensed fuel grade managed by the FMS.",
    )
    fms_fuel_grade = fields.Selection(
        selection=[
            ("UX", "Unleaded Extra (PMS)"),
            ("VP", "V-Power (PMS Premium)"),
            ("DX", "Diesel Extra (AGO)"),
            ("DPK", "Kerosene (DPK)"),
        ],
        string="Fuel Grade",
        help=(
            "EPRA fuel grade code.  Must be set on all products where "
            "fms_is_fuel_product is True."
        ),
    )
