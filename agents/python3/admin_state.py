import asyncio
from typing import Union
import websockets
import json

from websockets.client import WebSocketClientProtocol

_move_set = set(("up", "down", "left", "right"))


class AdminState:
    def __init__(self, connection_string: str):
        self._game_count = 1
        self._connection_string = connection_string
        self._state = None
        self._tick_callback = None

        # Variables for a reward function
        self._winner = None # Either "a" or "b"
        self._total_ticks = 0 # Total number of ticks in the game
        self._a_invalid_moves = 0 # Not implemented
        self._a_valid_moves = 0 # Not implemented
        self._a_agents = [] # List of tuples per unit (unit_id, hp, initial_position, final_position, bombs_used)
        self._b_invalid_moves = 0 # Not implemented
        self._b_valid_moves = 0 # Not implemented
        self._b_agents = [] # List of tuples per unit (unit_id, hp, initial_position, final_position, bombs_used)

    def set_game_tick_callback(self, generate_agent_action_callback):
        self._tick_callback = generate_agent_action_callback

    def save_vars_from_state_to_disk(self):
        def agent_dict(agent_data):
            return {
                "hp": agent_data[1],
                "initial_position": agent_data[2],
                "final_position": agent_data[3],
                "bombs_used": agent_data[4]
            }
        
        dict_to_save = {
            "winner": self._winner,
            "total_ticks": self._total_ticks,
            "a": {
                "invalid_moves": self._a_invalid_moves,
                "valid_moves": self._a_valid_moves,
                **{str(self._a_agents[i][0]): agent_dict(self._a_agents[i]) for i in range(3)}
            },
            "b": {
                "invalid_moves": self._b_invalid_moves,
                "valid_moves": self._b_valid_moves,
                **{str(self._b_agents[i][0]): agent_dict(self._b_agents[i]) for i in range(3)}
            }
        }

        with open(f"/app/data/game{self._game_count}.txt", "w") as file:
            file.write(json.dumps(dict_to_save))

    def reset_vars(self):
        self._winner = None
        self._total_ticks = 0
        self._unit_hps = {}
        self._a_invalid_moves = 0
        self._a_valid_moves = 0
        self._a_agents = []
        self._b_invalid_moves = 0
        self._b_valid_moves = 0
        self._b_agents = []

    def parse_endgame_state(self, payload):
        self._winner = payload.get("winning_agent_id")
        self._total_ticks = payload.get("history")[-1].get("tick")
        self._unit_hps = self.get_damage_dealt(payload)

        agents_a = self._state.get("agents").get("a").get("unit_ids")
        for agent in agents_a:
            unit_state = self._state.get("unit_state").get(agent)
            payload_unit_state = payload.get("initial_state").get("unit_state").get(agent)
            bombs_used = payload_unit_state.get("inventory").get("bombs") - unit_state.get("inventory").get("bombs")
            self._a_agents.append((unit_state.get("unit_id"), unit_state.get("hp"), payload_unit_state.get("coordinates"), unit_state.get("coordinates"), bombs_used))

        agents_b = self._state.get("agents").get("b").get("unit_ids")
        for agent in agents_b:
            unit_state = self._state.get("unit_state").get(agent)
            payload_unit_state = payload.get("initial_state").get("unit_state").get(agent)
            bombs_used = payload_unit_state.get("inventory").get("bombs") - unit_state.get("inventory").get("bombs")
            self._b_agents.append((unit_state.get("unit_id"), unit_state.get("hp"), payload_unit_state.get("coordinates"), unit_state.get("coordinates"), bombs_used))

    # Wytse with the sauce
    def get_damage_dealt(self, payload):
        unit_hps = {}

        for unit in payload.get("initial_state").get("unit_state"):
            unit_hps[unit] = payload.get("initial_state").get("unit_state").get(unit).get("hp")

        for tick in payload.get("history"):
            tick_id = tick.get("tick")
            events = tick.get("events")

            for event in events:
                if(event.get("type") == "unit_state"):
                    affected_unit = event.get("data").get("unit_id")
                    affected_unit_hp = unit_hps[affected_unit]
                    affected_unit_current_hp = event.get("data").get("hp")

                    if(affected_unit_hp != affected_unit_current_hp):
                        print(f"{affected_unit} took damage on tick {tick_id}. Remaining HP: {affected_unit_current_hp}") # Convert to dict?
                        unit_hps[affected_unit] = affected_unit_current_hp
        return unit_hps

    async def connect(self):
        self.connection = await websockets.connect(self._connection_string)
        if self.connection.open:
            return self.connection

    async def _send(self, packet):
        await self.connection.send(json.dumps(packet))

    async def _handle_messages(self, connection: WebSocketClientProtocol):
        while True:
            try:
                raw_data = await connection.recv()
                data = json.loads(raw_data)
                await self._on_data(data)
            except websockets.exceptions.ConnectionClosed:
                print('Connection with server closed')
                break

    async def _on_data(self, data):
        data_type = data.get("type")

        if data_type == "info":
            # no operation
            pass
        elif data_type == "game_state":
            payload = data.get("payload")
            self._on_game_state(payload)
        elif data_type == "tick":
            payload = data.get("payload")
            await self._on_game_tick(payload)

        elif data_type == "endgame_state":
            payload = data.get("payload")
            self.parse_endgame_state(payload)
            print(f"Game over. Winner: Agent {self._winner}")
            self.save_vars_from_state_to_disk()
            self.reset_vars()

            if self._game_count < 2:
                await self._send({"type": "request_game_reset", "world_seed": 1234, "prng_seed": 1234})
                self._game_count += 1
                print(f"Game reset requested to start game {self._game_count}")
            else:
                print("Game count limit reached. Exiting.")
        else:
            print(f"unknown packet \"{data_type}\": {data}")

    def _on_game_state(self, game_state):
        self._state = game_state

    async def _on_game_tick(self, game_tick):
        events = game_tick.get("events")
        for event in events:
            event_type = event.get("type")
            if event_type == "entity_spawned":
                self._on_entity_spawned(event)
            elif event_type == "entity_expired":
                self._on_entity_expired(event)
            elif event_type == "unit_state":
                payload = event.get("data")
                self._on_unit_state(payload)
            elif event_type == "entity_state":
                x, y = event.get("coordinates")
                updated_entity = event.get("updated_entity")
                self._on_entity_state(x, y, updated_entity)
            elif event_type == "unit":
                unit_action = event.get("data")
                self._on_unit_action(unit_action)
            else:
                print(f"unknown event type {event_type}: {event}")
        if self._tick_callback is not None:
            tick_number = game_tick.get("tick")
            self._state["tick"] = tick_number
            await self._tick_callback(tick_number, self._state)

    def _on_entity_spawned(self, spawn_event):
        spawn_payload = spawn_event.get("data")
        self._state["entities"].append(spawn_payload)

    def _on_entity_expired(self, spawn_event):
        expire_payload = spawn_event.get("data")

        def filter_entity_fn(entity):
            [x, y] = expire_payload
            entity_x = entity.get("x")
            entity_y = entity.get("y")
            should_remove = entity_x == x and entity_y == y
            return should_remove == False

        self._state["entities"] = list(filter(
            filter_entity_fn, self._state["entities"]))

    def _on_unit_state(self, unit_state):
        unit_id = unit_state.get("unit_id")
        self._state["unit_state"][unit_id] = unit_state

    def _on_entity_state(self, x, y, updated_entity):
        for entity in self._state.get("entities"):
            if entity.get("x") == x and entity.get("y") == y:
                self._state["entities"].remove(entity)
        self._state["entities"].append(updated_entity)

    def _on_unit_action(self, action_packet):
        unit_id = action_packet["unit_id"]
        unit = self._state["unit_state"][unit_id]
        coordinates = unit.get("coordinates")
        action_type = action_packet.get("type")
        if action_type == "move":
            move = action_packet.get("move")
            if move in _move_set:
                new_coordinates = self._get_new_unit_coordinates(
                    coordinates, move)
                self._state["unit_state"][unit_id]["coordinates"] = new_coordinates
        elif action_type == "bomb":
            # no - op since this is redundant info
            pass
        elif action_type == "detonate":
            # no - op since this is redundant info
            pass
        else:
            print(f"Unhandled agent action recieved: {action_type}")

    def _get_new_unit_coordinates(self, coordinates, move_action) -> Union[int, int]:
        [x, y] = coordinates
        if move_action == "up":
            return [x, y+1]
        elif move_action == "down":
            return [x, y-1]
        elif move_action == "right":
            return [x+1, y]
        elif move_action == "left":
            return [x-1, y]