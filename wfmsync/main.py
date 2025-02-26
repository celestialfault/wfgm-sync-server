import logging
import os
from contextlib import asynccontextmanager

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.responses import RedirectResponse

from wfmsync import common
from wfmsync.db import init_db
from wfmsync.routes.v1 import v1
from wfmsync.routes.v2 import v2


@asynccontextmanager
async def lifecycle(_):
    common.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4))
    load_dotenv()
    await init_db()

    if "SILENCE_ACCESS_LOGS" in os.environ:
        logging.getLogger("uvicorn.access").disabled = True

    yield

    await common.session.close()


app = FastAPI(lifespan=lifecycle)
app.mount("/v2", v2)
app.mount("/", v1)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("https://modrinth.com/mod/female-gender")
