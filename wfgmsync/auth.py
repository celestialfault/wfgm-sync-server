import secrets
from datetime import datetime, timezone
from uuid import UUID

from pydantic import UUID4

from . import common
from .db import UserAuth


class AuthenticationError(RuntimeError):
    message: str
    response_code: int


class InvalidAuthenticationError(AuthenticationError):
    def __init__(self, message: str, response_code: int = 403):
        self.message = message
        self.response_code = response_code


class AuthServerError(AuthenticationError):
    def __init__(self, message: str):
        self.message = message
        self.response_code = 503


async def authenticate(token: str | None, username: str | None, server_id: str | None) -> UserAuth:
    if token is not None:
        auth = await UserAuth.find_one(UserAuth.token == token)
        if auth is None:
            raise InvalidAuthenticationError(
                "The provided authentication token is invalid or has expired"
            )
        return auth

    if username is None or server_id is None:
        raise InvalidAuthenticationError(
            "An authentication token or Mojang authentication is required", 401
        )

    return await authenticate_from_mojang(username, server_id)


async def authenticate_from_mojang(username: str, server_id: str) -> UserAuth:
    if username is None or server_id is None:
        raise InvalidAuthenticationError(
            "An authentication token or session server authentication is required", 401
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
            raise AuthServerError(
                f"Session servers returned an unexpected response: status {response.status}"
            )
        json = await response.json()
        if not json or "id" not in json:
            raise InvalidAuthenticationError(
                "Couldn't authenticate you against the Mojang session servers; did you forget"
                " to send a join server request?"
            )
        return UUID(json["id"])
