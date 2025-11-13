from typing import Any, Awaitable, Callable, Dict, cast
from urllib.parse import parse_qs

import jwt
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken


@database_sync_to_async  # type: ignore[misc]
def get_user(validated_token: Dict[str, Any]) -> AbstractBaseUser:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user: AbstractBaseUser = User.objects.get(id=validated_token[cast(str, settings.SIMPLE_JWT["USER_ID_CLAIM"])])
        return user
    except User.DoesNotExist:
        return cast(AbstractBaseUser, AnonymousUser())


class JWTAuthMiddleware:
    def __init__(
        self, app: Callable[[Dict[str, Any], Callable[..., Any], Callable[..., Any]], Awaitable[None]]
    ) -> None:
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        query_string = parse_qs(scope["query_string"].decode("utf8"))
        token = query_string.get("token")

        if not token:
            scope["user"] = AnonymousUser()
            return await self.app(scope, receive, send)

        try:
            UntypedToken(token[0])
        except (InvalidToken, TokenError) as e:
            print(e)
            scope["user"] = AnonymousUser()
            return await self.app(scope, receive, send)

        decoded_data: Dict[str, Any] = jwt.decode(token[0], str(settings.SECRET_KEY), algorithms=["HS256"])
        scope["user"] = await get_user(decoded_data)

        return await self.app(scope, receive, send)
