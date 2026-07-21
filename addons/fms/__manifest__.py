{
    "name": "Forecourt Management System (FMS)",
    "version": "18.0.1.0.0",
    "depends": ["stock", "point_of_sale", "account", "hr", "purchase", "sale", "mail"],
    "data": [
        # 1. Security — ACLs before views reference model_ids
        "security/ir.model.access.csv",
        # 2. Seed data (noupdate=1 — created once, never overwritten on upgrade)
        "data/ir_sequence_data.xml",
        "data/product_data.xml",
        "data/tank_data.xml",
        "data/pump_data.xml",
        "data/calibration_chart_data.xml",
        # 3. Views + actions (actions must exist before menus reference them)
        "views/fms_site_preferences_views.xml",
        "views/product_template_views.xml",
        "views/stock_location_views.xml",
        "views/fms_pump_views.xml",
        "views/fms_calibration_chart_views.xml",
        "views/fms_shift_views.xml",
        "views/fms_meter_reading_views.xml",
        # 4. Menus last
        "views/fms_menus.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
}
