# 3D Print Cost Calculator

A Flask 3 application for transparent FDM and resin 3D-print quoting. It calculates material, labor, power, printer depreciation, maintenance, waste, failure reserve, hardware, packaging, setup, overhead, tax, unit cost, and suggested sale prices.

## Features

- Anonymous cost calculation; no account is required to calculate a quote.
- FDM/filament and resin material presets, including PLA, PETG, ABS, ASA, TPU, and Resin.
- Multiple material lines for multi-material prints.
- Batch quantity, print time, labor time, labor rate, power, electricity, printer depreciation, maintenance, waste, failure reserve, overhead, tax, hardware, packaging, and setup inputs.
- Cost breakdown, per-part cost, configurable currency display, and suggested prices for 25%, 40%, 60%, 80%, or a custom margin.
- `/healthz` endpoint for application and SQLite readiness checks.
- Optional Keycloak/OpenID Connect sign-in for account-scoped preferences, material presets, printer profiles, and quote history.

## Anonymous and signed-in behavior

Anonymous use is the default. The calculator and `POST /api/calculate` work without OIDC configuration or an account. Anonymous calculations are not written to the SQLite persistence tables; keep or export a draft locally before closing the browser.

When Keycloak OIDC is configured and a user signs in, the application stores the OIDC `sub` as the owner ID. Preferences, material presets, printer profiles, and quotes are then read and written per signed-in user. The persistence API returns `401` to anonymous callers. Signing out clears the Flask session; it does not delete that user's database records.

There is no paywall, subscription, payment flow, or usage limit. All calculator functionality remains available without signing in. Sign-in only enables persistence and account-scoped saved data.

## Calculation semantics

The API accepts bounded numeric inputs. Invalid or missing numeric values use the documented defaults; values outside the supported ranges are clamped. Print and labor minutes are converted to fractional hours (`hours + minutes / 60`). Up to 20 material lines are processed.

For each material line, grams are used when supplied. Otherwise, volume in millilitres is converted to grams using density. Material cost is the sum of `grams × cost_per_gram`. The calculation then applies:

```text
material_with_waste = material_cost_per_part × (1 + waste_rate) × quantity
labor               = labor_hours_per_part × labor_rate × quantity + setup_labor
electricity         = print_hours_per_part × quantity × power_watts / 1000 × electricity_rate
depreciation        = print_hours_per_part × quantity × printer_cost / printer_life_hours
maintenance         = print_hours_per_part × quantity × maintenance_rate
failure_reserve     = (material_with_waste + labor + electricity + depreciation + maintenance)
                      × failure_rate
hardware            = hardware_per_part × quantity
packaging           = packaging_per_part × quantity
direct              = material_with_waste + labor + electricity + depreciation + maintenance
                      + failure_reserve + hardware + packaging + setup_cost
overhead            = direct × overhead_rate
before_tax          = direct + overhead
tax                 = before_tax × tax_rate
total               = before_tax + tax
unit_cost           = total / quantity
suggested_price     = unit_cost / (1 - margin)
```

Rates are percentages where the UI labels them as percentages. Suggested prices use margins of 25%, 40%, 60%, 80%, and the requested custom margin. API monetary results are rounded to two decimal places. The default material prices are PLA `$0.05/g`, PETG `$0.06/g`, TPU `$0.07/g`, ABS `$0.08/g`, ASA `$0.09/g`, and Resin `$0.10/g`.

## Configuration

### SQLite and Flask session

- `DATABASE_PATH` — optional SQLite file path. Default: `data/calculator.db` relative to the application directory. Mount or persist the containing directory in deployments.
- `SECRET_KEY` — required for stable, secure Flask sessions and required before OIDC login is enabled. Set a long random value; do not use the development fallback in a persistent deployment.

### Keycloak / OIDC

Set all five variables to enable the sign-in link:

| Variable | Meaning |
| --- | --- |
| `OIDC_ISSUER_URL` | Keycloak realm issuer URL, for example `https://sso.example.com/realms/printwise` |
| `OIDC_CLIENT_ID` | Keycloak client ID |
| `OIDC_CLIENT_SECRET` | Keycloak confidential-client secret |
| `OIDC_REDIRECT_URI` | Exact public callback URL, for example `https://calculator.example.com/auth/callback` |
| `SECRET_KEY` | Flask session signing key |

The application discovers the authorization, token, and user-info endpoints from `${OIDC_ISSUER_URL}/.well-known/openid-configuration`. Configure the Keycloak client's valid redirect URI to exactly match `OIDC_REDIRECT_URI`. The callback path implemented by this application is:

```text
/auth/callback
```

For local Keycloak testing, an example callback value is `http://localhost:5000/auth/callback`. Do not put `OIDC_CLIENT_SECRET` in source control or image layers.

## Local development

Python 3.11 and a virtual environment are recommended. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Run the Flask development server:

```sh
SECRET_KEY=local-development-only \
DATABASE_PATH="$PWD/data/calculator.db" \
.venv/bin/python app.py
```

The application listens on `http://127.0.0.1:5000` (and binds all interfaces when launched by `app.py`). OIDC is optional for local calculation. Add the five OIDC variables above only when testing Keycloak login.

### Local test and smoke check

Run the checked-in standard-library test suite and syntax check:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q app.py tests
```

With the server running, check SQLite readiness and the calculation API:

```sh
curl --fail http://127.0.0.1:5000/healthz
curl --fail \
  -H 'Content-Type: application/json' \
  -d '{"quantity":1,"material_lines":[{"name":"PLA","grams":100,"cost_per_gram":0.05}],"print_hours":1}' \
  http://127.0.0.1:5000/api/calculate
```

Expected health output is JSON containing `{"status":"ok"}`. Stop the development server with `Ctrl-C`.

## Docker

Build the production image:

```sh
docker build -t 3d-print-cost-calculator .
```

Run it with a persistent local SQLite directory:

```sh
docker run --rm --name 3d-print-cost-calculator \
  -p 5000:5000 \
  -e SECRET_KEY='replace-with-a-long-random-value' \
  -e DATABASE_PATH=/app/data/calculator.db \
  -v "$PWD/data:/app/data" \
  3d-print-cost-calculator
```

Open `http://localhost:5000`. The image runs Gunicorn as a non-root user and binds `0.0.0.0:5000`. The image health check requests `/healthz` with Python's standard library, so it does not depend on `curl` being installed.

## Deployment

Production is deployed to k3s through the separate `home-infra` GitOps repository. Application changes are published as immutable GHCR images, then pinned in the ArgoCD-managed manifest. Do not patch the live Deployment directly.

## License

MIT. See [LICENSE](LICENSE).
