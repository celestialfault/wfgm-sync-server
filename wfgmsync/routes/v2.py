from typing import Annotated

from beanie.odm.operators.find.comparison import In
from fastapi import FastAPI, Header, Response
from pydantic import UUID4
from starlette.responses import JSONResponse, PlainTextResponse

from wfgmsync.auth import authenticate, AuthenticationError
from wfgmsync.db import UserConfig, User
from wfgmsync.models import SuccessResponse, ErrorResponse, BulkQueryResponse

app = FastAPI(docs_url="/", version="2.0.0")


# I'd still love it if QUERY wasn't stuck in RFC draft hell :(
@app.post(
    "/bulk-query",
    summary="Bulk query user data",
    responses={200: {"model": BulkQueryResponse}, 400: {"model": ErrorResponse}},
)
async def bulk_query(body: set[UUID4]):
    """Query user data for multiple UUIDs at once

    This route requires at least 2 unique UUIDs, and at most 20 per request.
    """
    if len(body) < 2 or len(body) > 20:
        return JSONResponse(
            content={"success": False, "error": "This route requires between 2-20 unique UUIDs"},
            status_code=400,
        )

    return BulkQueryResponse(
        users={x.uuid: x.data async for x in User.find_many(In(User.uuid, body))}
    )


@app.get("/user/{uuid}", summary="Query user data", responses={200: {"model": UserConfig}, 204: {}})
async def query(uuid: UUID4):
    user = await User.find_one(User.uuid == uuid)
    # abusing python language quirks to save on an entire one if statement
    return user and user.data or PlainTextResponse(status_code=204)


@app.put(
    "/user/{uuid}",
    summary="Update user data",
    responses={
        200: {
            "model": SuccessResponse,
            "headers": {
                "Auth-Token": {
                    "schema": {"type": "string"},
                    "description": "An authentication token to use in future requests",
                }
            },
        },
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def update(
    uuid: UUID4,
    body: UserConfig,
    response: Response,
    auth_token: Annotated[str | None, Header()] = None,
    moj_auth_username: Annotated[str | None, Header()] = None,
    moj_auth_server: Annotated[str | None, Header()] = None,
):
    """Update the stored configuration for a given user

    At least one of either `Auth-Token` or *both* `Moj-Auth-Username` __and__ `Moj-Auth-Server`
    **must** be provided, or this route will return a 401 Unauthorized.

    An `Auth-Token` may be obtained by [authenticating with the Mojang session servers](https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Protocol_Encryption#Authentication),
    and using the `Moj-Auth-*` headers with the relevant values.

    The provided auth token will expire after 1 hour, or when a new token is created by doing
    the same authentication flow again, whichever happens first.
    """
    try:
        auth = await authenticate(auth_token, moj_auth_username, moj_auth_server)
    except AuthenticationError as e:
        return JSONResponse(
            content={"success": False, "error": e.message},
            status_code=e.response_code,
        )

    if auth.uuid != uuid:
        return JSONResponse(
            content={
                "success": False,
                "error": "The provided authentication is not valid for the requested UUID",
            },
            status_code=403,
        )

    response.headers["Auth-Token"] = auth.token
    user = await User.find_one_or_create(uuid)
    await user.set({User.data: body})
    return SuccessResponse()
