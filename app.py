import uvicorn
from fastapi import FastAPI
from src.autres import data_workflow

app = FastAPI()

# Route to input data and get data to plot
@app.get("/plots")
def show_plots():
    y = data_workflow()
    return {"y to send to plot_workflow": y}

# Route to test giving an argument: change message basd in input
@app.get("/message/{msg}")
def change_msg(msg: str) -> dict:
    return {"message": f"Hello World custom: {msg}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)