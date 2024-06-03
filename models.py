import logging
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

logging.info("SQLAlchemy initialized.")

class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_cost_pla = db.Column(db.Float, default=0.05)
    material_cost_petg = db.Column(db.Float, default=0.06)
    material_cost_tpu = db.Column(db.Float, default=0.07)
    material_cost_abs = db.Column(db.Float, default=0.08)
    labor_hourly_rate = db.Column(db.Float, default=20.0)
    machine_hourly_cost = db.Column(db.Float, default=0.15)

logging.info("UserPreferences model defined.")
