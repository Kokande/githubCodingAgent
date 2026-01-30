import sys
import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request

app = FastAPI(title="Coding Agent")
logger = logging.getLogger(__name__)
log_config = uvicorn.config.LOGGING_CONFIG
log_config["formatters"]["access"]["fmt"] = '%(asctime)s - %(levelname)s - %(message)s'
log_config["formatters"]["default"]["fmt"] = '%(asctime)s - %(levelname)s - %(message)s'


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Log to console
        logging.FileHandler('webhook.log')  # Log to file
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up GitHub Webhook Service...")
    yield
    logger.info("Shutting down...")


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "GitHub Webhook Receiver",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "POST /webhook",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }


@app.get("/agent/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def github_webhook(request: Request):
    try:
        x_github_event = request.headers.get("X-GitHub-Event")
        x_hub_signature_256 = request.headers.get("X-Hub-Signature-256")

        logger.info(f"Event header: {x_github_event}")
        logger.info(f"Signature header: {x_hub_signature_256}")

        body = await request.body()
        body_str = body.decode('utf-8')

        logger.info(f"Body preview: {body_str[:500]}...")

        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON"}
            )

        if x_github_event == "ping":
            logger.info("Received ping event")
            return {"message": "pong"}

        if x_github_event == "issues":
            action = payload.get("action")
            logger.info(f"Received issues event with action: {action}")

            if action == "opened":
                # Agent
                return {"status": "processed"}

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Error in webhook handler: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        log_config=log_config,
        access_log=True
    )