import secrets
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import UUID4
from starlette import status

from wfgmsync import common
from wfgmsync.db import UserAuth

api_key = APIKeyHeader(
    name="auth-token",
    auto_error=False,
    description="Authentication token provided after successfully authenticating against the Mojang session servers",
)


async def authenticate(
    token: Annotated[str, Depends(api_key)] = None,
    username: Annotated[str, Header(alias="moj-auth-username")] = None,
    server_id: Annotated[str, Header(alias="moj-auth-server")] = None,
) -> UserAuth:
    if token is not None:
        auth = await UserAuth.find_one(UserAuth.token == token)
        if auth is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The provided auth token is invalid or has expired",
            )
        return auth

    if username is None or server_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="An authentication token or Mojang authentication is required",
        )

    return await create_mojang_auth(username, server_id)


async def create_mojang_auth(username: str, server_id: str) -> UserAuth:
    if username is None or server_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Both username and server id are required",
        )

    uuid = await validate_session_server(username, server_id)
    await UserAuth.find_many(UserAuth.uuid == uuid).delete_many()
    auth = UserAuth(
        uuid=uuid, token=secrets.token_urlsafe(32), created_at=datetime.now(timezone.utc)
    )
    # noinspection PyArgumentList
    await auth.insert()
    return auth


async def validate_session_server(username: str, server_id: str) -> UUID4:
    url = "https://sessionserver.mojang.com/session/minecraft/hasJoined"
    params = {"username": username, "serverId": server_id}
    async with common.session.get(url, params=params) as response:
        if response.status >= 400:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Session servers returned an unexpected response: status {response.status}",
            )

        json = await response.json()
        if not json or "id" not in json:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Couldn't authenticate you against the Mojang session servers; did you forget"
                    " to send a join server request?"
                ),
            )

        return UUID(json["id"])
