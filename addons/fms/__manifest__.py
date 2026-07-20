{
    "name": "Forecourt Management System (FMS)",
    "version": "18.0.1.0.0",
    "depends": ["stock", "point_of_sale", "account", "hr", "purchase", "sale", "mail"],
    "data": [
        # 1. Security — ACLs before views reference model_ids
        "security/ir.model.access.csv",
        # 2. Seed data (noupdate=1 — created once, never overwritten on upgrade)
        "data/product_data.xml",
        # 3. Views + actions (before menus reference action IDs)
        "views/fms_site_preferences_views.xml",
        "views/product_template_views.xml",
        # 4. Menus last
        "views/fms_menus.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
}
