import os
from typing import Annotated

from fastapi import FastAPI, Depends
from fastapi.security import APIKeyHeader
from pydantic import UUID4
from starlette.responses import PlainTextResponse, JSONResponse

from wfgmsync.db import ContributorNametag, User
from wfgmsync.models import SuccessResponse, ErrorResponse

app = FastAPI(
    docs_url="/",
    description="""
Internal endpoints for managing contributor nametags through Discord; these routes are not
intended for public consumption.
""",
)
api_key = APIKeyHeader(name="auth-token")


async def contributors():
    # noinspection PyComparisonWithNone
    return {x.uuid: x.nametag async for x in User.find(User.nametag != None)}


@app.put(
    "/{uuid}",
    response_model=SuccessResponse,
    responses={401: {}, 403: {}},
    summary="Update contributor nametag",
)
async def update_contributor(
    uuid: UUID4, auth_token: Annotated[str, Depends(api_key)], body: ContributorNametag
):
    """Internal endpoint, updates the nametag stored for a contributor"""
    if auth_token != os.environ["ADMIN_TOKEN"]:
        return PlainTextResponse(status_code=401)

    user = await User.find_one(User.uuid == uuid)
    if user is None:
        user = User(uuid=uuid, data=None)
        # noinspection PyArgumentList
        await user.insert()
    await user.set({User.nametag: body})

    return {"success": True}


@app.delete(
    "/{uuid}",
    response_model=SuccessResponse,
    responses={401: {}, 403: {}, 404: {"model": ErrorResponse}},
    summary="Delete contributor nametag",
)
async def delete_contributor(uuid: UUID4, auth_token: Annotated[str, Depends(api_key)]):
    """Internal endpoint, deletes any nametag stored for a contributor"""
    if auth_token != os.environ["ADMIN_TOKEN"]:
        return PlainTextResponse(status_code=401)

    user = await User.find_one(User.uuid == uuid)
    if user is None:
        return JSONResponse(
            status_code=404, content={"success": False, "error": "No such user exists"}
        )
    if user.nametag is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "That user doesn't have a contributor nametag"},
        )

    await user.set({User.nametag: None})
    return {"success": True}
