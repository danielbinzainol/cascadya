# Scaleway Monthly Cost Scanner

This project gives you a modular Python scanner that inventories your current Scaleway resources and estimates the monthly cost of what exists right now.
It now ships with a local web dashboard built with Vue and served by a Python backend on `localhost`.

It is built for the use case you described:

- scan all VMs
- identify VM type and RAM
- scan root and data volumes
- scan flexible IPv4 addresses
- scan Object Storage buckets and total stored size
- scan security groups and attached VMs
- refresh the estimate with one button
- export a JSON, CSV, and Markdown report

## What the tool does

The scanner combines:

- Scaleway Instance API for servers, local volumes, and flexible IPv4
- Scaleway Block Storage API for SBS volumes
- Scaleway Object Storage via the S3-compatible API for bucket size
- a local pricing catalog for rates that are stable enough to keep in config

The result is a monthly estimate based on the currently existing resources, not on historical invoices.

## Project layout

- `app.py`: launches the local web UI on `http://127.0.0.1:8765`
- `scw_cost/config.py`: env and catalog loading
- `scw_cost/api.py`: Scaleway REST client
- `scw_cost/object_storage.py`: bucket scan
- `scw_cost/pricing.py`: pricing and money parsing
- `scw_cost/inventory.py`: resource collection and cost calculation
- `scw_cost/reporter.py`: JSON, CSV, and Markdown export
- `scw_cost/gui.py`: one-button refresh UI
- `scw_cost/webapp.py`: local HTTP API and static web serving
- `web/`: Vue dashboard assets

## Setup

1. Create a virtual environment:

```powershell
python -m venv .venv
```

2. Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Copy the example env file:

```powershell
Copy-Item .env.example .env
```

5. Fill your Scaleway credentials in `.env`.

Required for REST API:

- `SCW_SECRET_KEY`

Required for Object Storage scan:

- `SCW_ACCESS_KEY`
- `SCW_SECRET_KEY`

Optional:

- `SCW_ORGANIZATION_ID`
- `SCW_PROJECT_ID`
- `SCW_ZONES`
- `SCW_OBJECT_REGIONS`

If `SCW_PROJECT_ID` is set, the scanner also uses it to scope Object Storage calls for that project.

6. Launch the local web app:

```powershell
python app.py
```

Then open:

```text
http://127.0.0.1:8765
```

You can also run the web app from the module entrypoint:

```powershell
python -m scw_cost --web
```

You can also run the CLI mode:

```powershell
python -m scw_cost
```

And the legacy Tk desktop UI remains available with:

```powershell
python -m scw_cost --gui
```

## Output

Each refresh writes:

- `output/latest_report.json`
- `output/latest_report.csv`
- `output/latest_report.md`

## Pricing notes

The default `price_catalog.json` is intentionally editable.

Current defaults bundled in the repo:

- hours per month: `730`
- flexible IPv4: `0.004 EUR/hour`
- block storage 5K: `0.000118 EUR/GB/hour`
- block storage 15K: `0.000177 EUR/GB/hour`
- object storage standard multi-AZ: `0.00002 EUR/GB/hour`
- object storage standard one zone: `0.0000103 EUR/GB/hour`
- object storage glacier: `0.0000035 EUR/GB/hour`

## Known limits

- `l_ssd` local storage pricing is left configurable because the public docs do not expose a clean default per-GB rate for every scenario. If you use local volumes and want them priced, put the rate in `price_catalog.json`.
- `b_ssd` is treated as a best-effort 5K block rate by default.
- Object Storage scan can be slow on very large buckets because it walks objects to calculate stored bytes.
- If a bucket uses versioning, the scanner counts all object versions for a more realistic storage total.
- Project-level filtering is applied on compute and volumes.
- Object Storage is project-scoped in practice: it uses the API key preferred project by default, or `SCW_PROJECT_ID` if you set it.

## Good next step

If you want, the next iteration can add:

- current-month billing API comparison
- per-project dashboard
- HTML report
- scheduled refresh
- webhook or email alert when the estimate changes

## Notes for the web UI

- The dashboard is served locally by Python on `127.0.0.1`.
- The frontend uses Vue 3 from a CDN at runtime, so your browser needs internet access to load the Vue library.
- The backend API is exposed locally at `/api/report`, `/api/status`, and `/api/refresh`.
- The web UI now includes a copy-ready security-group panel with attached VM intel and rules preview.
- The top-level header now lets you switch between the Cost view and the Security Groups view.
