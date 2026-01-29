import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Coding Agent")


@app.get("/agent/health")
async def test():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)