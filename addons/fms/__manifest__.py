{
    "name": "Forecourt Management System (FMS)",
    "version": "18.0.1.0.0",
    "depends": ["stock", "point_of_sale", "account", "hr", "purchase", "sale", "mail"],
    "data": [
        # 1. Security — ACLs must load before views reference model_ids
        "security/ir.model.access.csv",
        # 2. Views (actions must exist before menus reference them)
        "views/fms_site_preferences_views.xml",
        # 3. Menus last (actions must already exist)
        "views/fms_menus.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
}
