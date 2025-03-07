from typing import Annotated

from fastapi import FastAPI, Header, Query
from pydantic import UUID4
from starlette.responses import JSONResponse, PlainTextResponse

from wfgmsync.auth import create_mojang_auth
from wfgmsync.db import User, UserConfig, UserAuth, ContributorNametag
from wfgmsync.models import BulkQueryResponse, ErrorResponse, SuccessResponse, AuthenticatedResponse
from wfgmsync.routes import contributors

app = FastAPI(
    docs_url="/",
    version="1.0.0",
    description="Older, less supported API routes; you should prefer using [v2](/v2/) in new applications.",
    # deprecated = True,  # TODO mark this as deprecated once there's enough usage of the v2 routes
)

app.get(
    "/contributors",
    response_model=dict[UUID4, ContributorNametag],
    summary="Get contributor nametags",
)(contributors.contributors)


@app.post("/", response_model=BulkQueryResponse, summary="Get data for multiple players")
async def get_multiple_players(body: set[UUID4]):
    """Get player data for up to 20 unique UUIDs at once

    Any provided UUIDs that the server doesn't have any sync data for will simply be omitted from
    the returned users object.
    """
    if len(body) < 2:
        return JSONResponse(
            status_code=400,
            content={
                "error": "This route requires at least 2 unique UUIDs to be provided",
            },
        )
    if len(body) > 20:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bulk queries have a limit of 20 unique UUIDs at once",
            },
        )

    return await BulkQueryResponse.find(body)


# TODO wiki.vg is no more; update the link in the docstring here with a minecraft.wiki one at some point
@app.get(
    "/auth",
    response_model=AuthenticatedResponse,
    responses={403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get authentication token",
)
async def get_auth(
    server_id: Annotated[str, Query(alias="serverId")], username: Annotated[str, Query()]
):
    """Retrieve an authentication token used for updating player data

    This route requires [authenticating with Mojang's session servers](https://wiki.vg/Protocol_Encryption#Authentication).

    The provided authentication token will expire after 1 hour.

    Any authentication tokens that haven't yet expired will be invalidated after obtaining a new token.
    """
    auth = await create_mojang_auth(username, server_id)
    return {
        "success": True,
        "token": auth.token,
        "account": auth.uuid,
        "expires": auth.created_at + UserAuth.EXPIRE_AFTER,
    }


@app.put(
    "/{uuid}",
    response_model=SuccessResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Update player data",
)
async def update_data(uuid: UUID4, auth_token: Annotated[str, Header()], body: UserConfig):
    """Stores the provided player data for the given authenticated user

    This requires an `Auth-Token` header provided from the `/auth` route.
    """
    auth = await UserAuth.find_one(UserAuth.token == auth_token)
    if not auth:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Authentication is invalid or has expired"},
        )
    if auth.uuid != uuid:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "The given authentication is not valid for the current user",
            },
        )

    user = await User.find_one_or_create(uuid)
    user.data = body
    # shut up pycharm
    # noinspection PyArgumentList
    await user.save()
    return {"success": True}


@app.get("/{uuid}", response_model=UserConfig, responses={404: {}}, summary="Get player data")
async def get_player(uuid: UUID4):
    user = await User.find_one(User.uuid == uuid)
    return user and user.data or PlainTextResponse(status_code=404)
