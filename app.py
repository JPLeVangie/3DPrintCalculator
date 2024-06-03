import logging
import sys

from flask import Flask, render_template, request, jsonify, redirect, url_for

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

try:
    from models import db, UserPreferences
except ImportError as e:
    logging.error(f"Error importing models: {e}")
    raise

import math

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///preferences.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

try:
    db.init_app(app)
except Exception as e:
    logging.error(f"Error initializing the database: {e}")
    raise

logging.info("App initialized and database configured.")

@app.before_first_request
def create_tables():
    logging.info("Creating database tables if they don't exist.")
    try:
        db.create_all()
    except Exception as e:
        logging.error(f"Error creating database tables: {e}")
        raise

def calculate_3d_print_cost(material_cost_per_gram, total_grams, printing_hours, printing_minutes, labor_hours, labor_minutes, labor_hourly_rate, machine_hourly_cost):
    total_material_cost = material_cost_per_gram * total_grams * 1.1
    total_printing_time_hours = printing_hours + (printing_minutes / 60)
    total_labor_time_hours = labor_hours + (labor_minutes / 60)
    total_labor_cost = total_labor_time_hours * labor_hourly_rate
    total_machine_cost = total_printing_time_hours * machine_hourly_cost
    full_cost = total_material_cost + total_labor_cost + total_machine_cost
    rounded_cost = math.floor(full_cost * 100) / 100  # Round down to the nearest cent
    return rounded_cost

@app.route('/', methods=['GET', 'POST'])
def index():
    logging.info("Index route accessed.")
    preferences = UserPreferences.query.first()
    if not preferences:
        logging.info("No preferences found, creating default preferences.")
        preferences = UserPreferences()
        db.session.add(preferences)
        db.session.commit()

    material_types = {
        "PLA": preferences.material_cost_pla,
        "PETG": preferences.material_cost_petg,
        "TPU": preferences.material_cost_tpu,
        "ABS": preferences.material_cost_abs,
    }

    if request.method == 'POST':
        material_type = request.form['material_type']
        material_cost_per_gram = material_types[material_type]
        total_grams = float(request.form['total_grams'])
        printing_hours = float(request.form['printing_hours'] or 0)
        printing_minutes = float(request.form['printing_minutes'] or 0)
        labor_hours = float(request.form['labor_hours'] or 0)
        labor_minutes = float(request.form['labor_minutes'] or 0)
        labor_hourly_rate = preferences.labor_hourly_rate
        machine_hourly_cost = preferences.machine_hourly_cost

        cost = calculate_3d_print_cost(material_cost_per_gram, total_grams, printing_hours, printing_minutes, labor_hours, labor_minutes, labor_hourly_rate, machine_hourly_cost)

        # Return the result as JSON for AJAX
        return jsonify({'cost': cost})

    return render_template('index.html', materials=material_types.keys())

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    logging.info("Settings route accessed.")
    preferences = UserPreferences.query.first()
    if not preferences:
        preferences = UserPreferences()
        db.session.add(preferences)
        db.session.commit()

    if request.method == 'POST':
        preferences.material_cost_pla = float(request.form['material_cost_pla'])
        preferences.material_cost_petg = float(request.form['material_cost_petg'])
        preferences.material_cost_tpu = float(request.form['material_cost_tpu'])
        preferences.material_cost_abs = float(request.form['material_cost_abs'])
        preferences.labor_hourly_rate = float(request.form['labor_hourly_rate'])
        preferences.machine_hourly_cost = float(request.form['machine_hourly_cost'])
        db.session.commit()
        return redirect(url_for('settings'))

    return render_template('settings.html', preferences=preferences)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
