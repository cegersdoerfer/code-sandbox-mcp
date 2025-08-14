from fastmcp.server.middleware import Middleware, MiddlewareContext
from contextvars import ContextVar
from typing import List, Optional
from urllib.parse import parse_qs

# Context variable for tags
tags_ctx: ContextVar[Optional[List[str]]] = ContextVar('tags', default=None)

context_id_ctx: ContextVar[Optional[str]] = ContextVar('context_id', default=None)


# Starlette server middleware
class HookTagMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Custom logic before processing the request
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        query_params = parse_qs(scope["query_string"].decode("utf-8"))
        tags = query_params.get("tag")
        tags_ctx.set(tags if tags else [])
        context_id = query_params.get("context_id")
        if type(context_id) == list:
            context_id = context_id[0]
        context_id_ctx.set(context_id if context_id else None)
        # Call the next middleware or application
        await self.app(scope, receive, send)


# Core MCP tools/list method hook
class FastMCPMiddleware(Middleware):

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        print(f"on_call_tool: {context}")
        context_id = context_id_ctx.get()
        if context_id:
            context.fastmcp_context.context_id = context_id
        else:
            context.fastmcp_context.context_id = None
        return await call_next(context)


    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = await call_next(context)
        tags_var = tags_ctx.get()
        if not tags_var:
            return tools

        filtered_tools = [tool for tool in tools if set(tags_var) & tool.tags]
        # also add any tools that have no tags
        filtered_tools.extend([tool for tool in tools if not tool.tags])
        return filtered_tools