from flask import Flask, render_template, request, jsonify
import math

app = Flask(__name__)

# Define material types and their costs per gram
material_types = {
    "PLA": 0.05,  # Cost per gram in USD
    "PETG": 0.06,
    "TPU": 0.07,
    "ABS": 0.08,
}

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
    if request.method == 'POST':
        material_type = request.form['material_type']
        material_cost_per_gram = material_types[material_type]
        total_grams = float(request.form['total_grams'])
        printing_hours = float(request.form['printing_hours'] or 0)
        printing_minutes = float(request.form['printing_minutes'] or 0)
        labor_hours = float(request.form['labor_hours'] or 0)
        labor_minutes = float(request.form['labor_minutes'] or 0)
        labor_hourly_rate = 20.0
        machine_hourly_cost = 0.15

        cost = calculate_3d_print_cost(material_cost_per_gram, total_grams, printing_hours, printing_minutes, labor_hours, labor_minutes, labor_hourly_rate, machine_hourly_cost)

        # Return the result as JSON for AJAX
        return jsonify({'cost': cost})

    return render_template('index.html', materials=material_types.keys())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
