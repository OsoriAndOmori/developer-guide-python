"""미니 FastAPI : 라우터 데코레이터 + 타입 힌트로 파라미터 주입

FastAPI(Starlette) 가 하는 일의 핵심만 담았다. ASGI 앱이므로 app(scope, receive, send) 형태다.
"""
import inspect
import json
from urllib.parse import parse_qsl


class MiniFastAPI:
    def __init__(self):
        self.routes = {}

    def get(self, path):  # @app.get("/path") 데코레이터
        def decorator(func):
            self.routes[("GET", path)] = func
            return func
        return decorator

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        handler = self.routes.get((scope["method"], scope["path"]))
        if handler is None:
            await self._respond(send, 404, {"error": "not found"})
            return
        try:
            kwargs = self._bind(handler, dict(parse_qsl(scope.get("query_string", b"").decode())))
        except (KeyError, ValueError) as e:
            await self._respond(send, 422, {"error": f"bad parameter: {e}"})
            return
        if inspect.iscoroutinefunction(handler):
            result = await handler(**kwargs)   # async def : 이벤트루프에서 직접 실행
        else:
            import asyncio
            result = await asyncio.to_thread(handler, **kwargs)  # def : 스레드로 보낸다 (FastAPI 가 하는 일)
        await self._respond(send, 200, result)

    @staticmethod
    def _bind(handler, query):
        """함수 시그니처의 타입 힌트를 읽어 쿼리 문자열을 그 타입으로 바꿔서 넘긴다."""
        kwargs = {}
        for name, param in inspect.signature(handler).parameters.items():
            if name in query:
                kwargs[name] = param.annotation(query[name]) if param.annotation is not inspect._empty else query[name]
            elif param.default is inspect._empty:
                raise KeyError(name)
        return kwargs

    @staticmethod
    async def _respond(send, status, data):
        body = json.dumps(data).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
