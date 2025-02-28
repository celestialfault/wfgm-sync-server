from typing import Annotated

from beanie.odm.operators.find.comparison import In
from fastapi import FastAPI, Header, Response
from pydantic import UUID4
from starlette.responses import JSONResponse, PlainTextResponse

from wfgmsync.auth import authenticate, AuthenticationError
from wfgmsync.db import UserConfig, User, UserAuth, ContributorNametag
from wfgmsync.models import SuccessResponse, ErrorResponse, BulkQueryResponse
from wfgmsync.routes import contributors

app = FastAPI(docs_url="/", version="2.0.0")

app.get(
    "/contributors",
    response_model=dict[UUID4, ContributorNametag],
    summary="Get contributor nametags",
)(contributors.contributors)


@app.post(
    "/bulk-query",
    summary="Bulk query user data",
    responses={200: {"model": BulkQueryResponse}, 400: {"model": ErrorResponse}},
)
async def bulk_query(body: set[UUID4]):
    """
    Query user data for multiple UUIDs at once

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
    # abusing python language quirks to save a single if statement
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
                },
                "Auth-Expires": {
                    "schema": {"type": "string"},
                    "description": "An ISO-8601 formatted timestamp indicating when the provided auth token expires",
                },
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
    """
    Update the stored configuration for a given user

    Either `Auth-Token` or *both* `Moj-Auth-Username` __and__ `Moj-Auth-Server`
    **must** be provided, or this route will return a 401 Unauthorized.

    If all three are provided, only `Auth-Token` will be considered, even if it's
    invalid or expired.

    An `Auth-Token` will be provided in the response headers on every successful request,
    along with an `Auth-Expiry` defining when the provided token will expire.

    To obtain an authentication token, first
    [authenticate with the Mojang session servers](https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Protocol_Encryption#Authentication)
    and use the `Moj-Auth-*` headers with the relevant values.

    The provided token will expire as indicated in the `Auth-Expiry` response header,
    or when a new authentication token is created by repeating the same Mojang
    authentication steps, whichever of the two happens first.
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
    auth_expiry = auth.created_at + UserAuth.EXPIRE_AFTER
    # datetime is a library from hell
    # despite having an .isoformat() method, it outputs a slightly different variation
    # of the ISO-8601 format that java's DateTimeFormatter.ISO_INSTANT does not parse.
    # more specifically, python formats them as '2025-02-27T16:48:29.141420+00:00',
    # whereas java expects '2025-02-27T16:48:29Z'.
    # similarly, python handles timestamps as floats, storing the millisecond
    # in the decimal place, instead of doing the reasonable thing of "just use a long
    # or bigint like everyone else does for unix timestamps".
    # xkcd 927 always applies. _always_.
    response.headers["Auth-Expires"] = auth_expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

    user = await User.find_one_or_create(uuid)
    await user.set({User.data: body})
    return SuccessResponse()
