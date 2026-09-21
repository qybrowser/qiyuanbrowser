"""Automate the existing Firefox environment with WebDriver BiDi directly."""

import asyncio
import json
import websockets
from _api import close_browser, open_browser

CODE = "d72cd8bd2209e2697b28234efaead8d1"
URL = "https://example.com"


async def automate(endpoint):
    async with websockets.connect(endpoint, open_timeout=10) as connection:
        serial = 0

        async def command(method, params):
            nonlocal serial
            serial += 1
            request_id = serial
            await connection.send(json.dumps({"id": request_id, "method": method, "params": params}))
            while True:
                reply = json.loads(await connection.recv())
                if reply.get("id") != request_id:
                    continue  # BiDi events are asynchronous.
                if reply.get("type") != "success":
                    raise RuntimeError(reply)
                return reply["result"]

        await command("session.new", {"capabilities": {}})
        tab = await command("browsingContext.create", {"type": "tab"})
        context = tab["context"]
        await command("browsingContext.navigate", {"context": context, "url": URL, "wait": "complete"})
        title = await command("script.evaluate", {
            "expression": "document.title",
            "target": {"context": context},
            "awaitPromise": True,
        })
        print({"title": title["result"].get("value"), "url": URL})


if __name__ == "__main__":
    opened = open_browser(CODE, "firefox")
    try:
        asyncio.run(automate(opened["debug_endpoint"]))
    finally:
        close_browser(CODE)
