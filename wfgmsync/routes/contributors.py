import os
from typing import Annotated

from fastapi import FastAPI, Header
from pydantic import UUID4
from starlette.responses import PlainTextResponse, JSONResponse

from wfgmsync.db import ContributorNametag, User, UserConfig
from wfgmsync.models import SuccessResponse, ErrorResponse

app = FastAPI(
    docs_url="/",
    description="""
Internal endpoints for managing contributor nametags through Discord; these routes are not
intended for public consumption.
""",
)


@app.put(
    "/contributor/{uuid}",
    response_model=SuccessResponse,
    responses={401: {}},
    summary="Update contributor nametag",
)
async def update_contributor(
    uuid: UUID4, auth_token: Annotated[str, Header()], body: ContributorNametag
):
    """Internal endpoint, updates the nametag stored for a contributor"""
    if auth_token != os.environ["ADMIN_TOKEN"]:
        return PlainTextResponse(status_code=401)

    user = await User.find_one(User.uuid == uuid)
    if user is None:
        user = User(uuid=uuid, data=UserConfig())
        # noinspection PyArgumentList
        await user.insert()
    await user.set({User.nametag: body})

    return {"success": True}


@app.delete(
    "/contributor/{uuid}",
    response_model=SuccessResponse,
    responses={401: {}, 404: {"model": ErrorResponse}},
    summary="Delete contributor nametag",
)
async def delete_contributor(uuid: UUID4, auth_token: Annotated[str, Header()]):
    """Internal endpoint, deletes any nametag stored for a contributor"""
    if auth_token != os.environ["ADMIN_TOKEN"]:
        return PlainTextResponse(status_code=401)

    user = await User.find_one(User.uuid == uuid)
    if user is None:
        return JSONResponse(
            status_code=404, content={"success": False, "error": "No such user exists"}
        )
    await user.set({User.nametag: None})

    return {"success": True}
