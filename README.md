# 3D Print Cost Calculator

This project is a web-based 3D Print Cost Calculator built using Flask and Bootstrap. It calculates the total cost of a 3D print based on the material type, total grams of material, printing time, and labor time.

![firefox_PMowKQD1dx](https://github.com/JPLeVangie/3DPrintCalculator/assets/47614776/9a758c8d-a2fc-4fac-a0c6-730ee585410a)



## Features

- Select material type from a dropdown list.
- Input total grams of material, printing hours, and minutes.
- Input labor hours and minutes.
- Calculate and display the total cost without refreshing the page.

## Prerequisites

- Docker
- Python 3.11

## Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/JPLeVangie/3DPrintCalculator.git
   cd 3DPrintCalculator
   ```

2. Build the Docker image:

   ```sh
   docker build -t 3d-print-cost-calculator .
   ```

3. Run the Docker container:

   ```sh
   docker run -p 5000:5000 3d-print-cost-calculator
   ```

4. Open your web browser and navigate to `http://localhost:5000`.

## Usage

1. Select the material type from the dropdown list.
2. Enter the total grams of material.
3. Enter the total printing hours and minutes.
4. Enter the total labor hours and minutes.
5. Click the "Calculate Cost" button to see the total cost displayed at the bottom of the page.

## Project Structure

```
3d-print-cost-calculator/
│
├── Dockerfile
├── README.md
├── app.py
├── requirements.txt
└── templates/
    └── index.html
```

## Technologies Used

- Python
- Flask
- Bootstrap
- jQuery
- Docker

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Bootstrap](https://getbootstrap.com/)
- [Flask](https://flask.palletsprojects.com/)
- [jQuery](https://jquery.com/)
