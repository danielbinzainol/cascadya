import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from src.ingest import data_workflow
from src.market_orders import complex_market_orders_data_workflow
from plots import plot_market_orders

"""
Use: run this file in debug mode, with F5.
Go to the local url, with "/docs": http://127.0.0.1:8000/docs
"""

app = FastAPI()

# Route to input data and get data to plot, with a project given in input
@app.get("/plots/{project}")
def show_plots(project:str):
    df = data_workflow(project)
    return {"df to send to plot_workflow": df}

# Route to test giving an argument: change message basd in input
@app.get("/message/{msg}")
def change_msg(msg: str) -> dict:
    return {"message": f"Hello World custom: {msg}"}

@app.get("/market-orders/{project}")
def call_complex_market_orders_data_workflow(project:str):
    paths = complex_market_orders_data_workflow(project)
    return paths

@app.get("/plot-market-orders")
def plot_mo(csv_path: str = Query(..., description="Absolute or relative path to the CSV file")):
    try:
        image_buffer = plot_market_orders(csv_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"CSV file not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(image_buffer, media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
