from uuid import UUID

from pydantic import UUID4

from . import common


class InvalidAuthenticationError(RuntimeError):
    message: str

    def __init__(self, message: str):
        self.message = message


class AuthServerError(RuntimeError):
    message: str

    def __init__(self, message: str):
        self.message = message


async def validate_session_server(server_id: str, username: str) -> UUID4:
    url = "https://sessionserver.mojang.com/session/minecraft/hasJoined"
    params = {"username": username, "serverId": server_id}
    async with common.session.get(url, params=params) as response:
        if response.status >= 400:
            raise AuthServerError(
                f"Session servers returned an unexpected response status {response.status}"
            )
        json = await response.json()
        if not json or "id" not in json:
            raise InvalidAuthenticationError("Couldn't authenticate with Mojang")
        return UUID(json["id"])
