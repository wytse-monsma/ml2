import json
from admin_state import AdminState
import asyncio
import time
import os

uri = os.environ.get(
    'GAME_CONNECTION_STRING') or "ws://127.0.0.1:3000/?role=admin&name=defaultName"

class Admin():
    def __init__(self):
        self._client = AdminState(uri)

        # any initialization code can go here
        self._client.set_game_tick_callback(self._on_game_tick)

        loop = asyncio.get_event_loop()
        connection = loop.run_until_complete(self._client.connect())
        tasks = [
            asyncio.ensure_future(self._client._handle_messages(connection)),
        ]
        loop.run_until_complete(asyncio.wait(tasks))

    async def _on_game_tick(self, tick_number, game_state):
        pass

def main():
    for i in range(0,10):
        while True:
            try:
                Admin()
            except:
                time.sleep(5)
                continue
            break

if __name__ == "__main__":
    main()