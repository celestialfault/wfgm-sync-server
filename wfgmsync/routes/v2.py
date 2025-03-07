from typing import Annotated

from fastapi import FastAPI, Depends
from fastapi.security import APIKeyHeader
from pydantic import UUID4
from starlette.responses import JSONResponse, PlainTextResponse

from wfgmsync.auth import authenticate
from wfgmsync.db import UserConfig, User, UserAuth, ContributorNametag
from wfgmsync.models import ErrorResponse, BulkQueryResponse, AuthenticatedResponse, SuccessResponse
from wfgmsync.routes import contributors

app = FastAPI(docs_url="/", version="2.0.0")
api_key = APIKeyHeader(
    name="auth-token",
    auto_error=False,
    description="Authentication token provided after successfully authenticating against the Mojang session servers",
)

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

    return await BulkQueryResponse.find(body)


@app.get(
    "/user/{uuid}",
    summary="Query user data",
    responses={200: {"model": UserConfig}, 204: {}},
)
async def query(uuid: UUID4):
    user = await User.find_one(User.uuid == uuid)
    return user and user.data or PlainTextResponse(status_code=204)


@app.put(
    "/user/{uuid}",
    summary="Update user data",
    responses={
        200: {"model": AuthenticatedResponse, "description": "Player data updated successfully"},
        401: {"model": ErrorResponse, "description": "Missing authentication headers"},
        403: {"model": ErrorResponse, "description": "Provided authentication is invalid"},
    },
)
async def update(uuid: UUID4, body: UserConfig, auth: Annotated[UserAuth, Depends(authenticate)]):
    """
    Update the stored configuration for a given user

    Either `Auth-Token` or *both* `Moj-Auth-Username` __and__ `Moj-Auth-Server`
    **must** be provided in the request headers, or this route will return
    401 Unauthorized.

    If all three are provided, only `Auth-Token` will be considered, even if it's
    invalid or expired.

    To obtain an authentication token, first
    [authenticate with the Mojang session servers](https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Protocol_Encryption#Authentication)
    and use the `Moj-Auth-*` headers with the relevant values.

    The provided token will expire as indicated by `expires`, or when a new authentication token
    is created by repeating the same Mojang authentication steps, whichever of the two
    happens first.
    """
    if auth.uuid != uuid:
        return JSONResponse(
            content={
                "success": False,
                "error": "The provided authentication is not valid for the requested UUID",
            },
            status_code=403,
        )

    user = await User.find_one_or_create(uuid)
    await user.set({User.data: body})

    auth_expiry = auth.created_at + UserAuth.EXPIRE_AFTER
    return {
        "success": True,
        "token": auth.token,
        "account": auth.uuid,
        # i hate date libraries. so much.
        # when an authentication token is first created, before it's ever stored in mongo,
        # this serializes to an ISO-8601 string that Java's DateTimeFormatter.ISO_INSTANT
        # can handle perfectly fine. every subsequent request that fetches this auth token
        # from mongo, it *explodes*. so, to fix that, just simply format the bare minimum part of
        # the string that we care about here ourselves.
        "expires": auth_expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# noinspection PyArgumentList
@app.delete(
    "/user/{uuid}",
    summary="Delete user data",
    responses={
        200: {"model": SuccessResponse, "description": "Player data deleted successfully"},
        401: {"model": ErrorResponse, "description": "Missing authentication headers"},
        403: {"model": ErrorResponse, "description": "Provided authentication is invalid"},
        404: {"model": ErrorResponse, "description": "No stored data exists for the given UUID"},
    },
)
async def delete(uuid: UUID4, auth: Annotated[UserAuth, Depends(authenticate)]):
    """
    Delete player data for the given UUID

    See `PUT /user/{uuid}` for documentation on authentication.

    Note that if the provided UUID has a contributor nametag (see `GET /contributors`),
    the requested user data will not be fully deleted; any future queries will still return
    no data regardless.
    """
    if auth.uuid != uuid:
        return JSONResponse(
            content={
                "success": False,
                "error": "The provided authentication is not valid for the requested UUID",
            },
            status_code=403,
        )

    user = await User.find_one({User.uuid: uuid})
    if not user or not user.data:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "No data exists for the requested UUID"},
        )

    if user.nametag is None:
        await user.delete()
    else:
        await user.set({User.data: None})

    return {"success": True}
