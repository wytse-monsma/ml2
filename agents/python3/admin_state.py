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
        self._winner = None
        self._num_of_blocks_destroyed_by_id = 0
        self._invalid_moves = 0
        self._valid_moves = 0
        self._total_ticks = []

    def set_game_tick_callback(self, generate_agent_action_callback):
        self._tick_callback = generate_agent_action_callback

    def save_vars_from_state_to_disk(self):
        dict_to_save = {
            "result": self._result,
            "num_of_blocks_destroyed_by_self": self._num_of_blocks_destroyed_by_self,
            "invalid_moves": self._invalid_moves,
            "valid_moves": self._valid_moves,
            "total_ticks": self._total_ticks
        }

        with open(f"/app/data/game{self._game_count}.txt", "w") as file:
            file.write(json.dumps(dict_to_save))

    def reset_vars(self):
        self._result = None
        self._num_of_blocks_destroyed_by_self = 0
        self._invalid_moves = 0
        self._valid_moves = 0
        self._total_ticks = []

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
            current_tick = payload.get("tick")
            self._total_ticks.append(current_tick)

        elif data_type == "endgame_state":
            payload = data.get("payload")
            winning_agent_id = payload.get("winning_agent_id")
            print(f"Game over. Winner: Agent {winning_agent_id}")
            self._result = winning_agent_id
            self.handle_reward(payload)

            if self._game_count < 5:
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
        # self.get_inflicted_damage(spawn_payload)

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
        self.get_cause_of_damage(unit_state)

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
        
    def get_cause_of_damage(self, unit_state):
        return
        # print('UNIT STATE:')
        # print(self._state["tick"])
        # print(unit_state)
        
        # get agent that took damage
        # get tick on which agent took damage
        # get coordinate on which agent took damage
        # check for explosions

    def get_inflicted_damage(self, spawn_payload):
        if(spawn_payload['type']) == 'x':
            sender = spawn_payload['unit_id']
            blast_radius = self._state['unit_state'][sender]['blast_diameter']
            print("UPDATED X ENTITY")
            print(blast_radius)

    def handle_reward(self, payload):
        # Initialize hp dictionary
        unit_hps = {}

        # Load initial hps
        for unit in payload.get("initial_state").get("unit_state"):
            unit_hps[unit] = payload.get("initial_state").get("unit_state").get(unit).get("hp")

        # Compare current hp in tick to stored hp in dictionary
        for tick in payload.get("history"):
            tick_id = tick.get("tick")
            events = tick.get("events")

            # Loop over events
            for event in events:
                if (event.get("type") == 'unit_state'):
                    # Unit that lost hp
                    affected_unit = event.get("data").get("unit_id")
                    # Stored hp of said unit
                    affected_unit_hp = unit_hps[affected_unit]
                    # hp of said unit in current tick
                    affected_unit_current_hp = event.get("data").get("hp")

                    # If there is a discrepancy --> it just lost hp
                    if(affected_unit_hp) != affected_unit_current_hp:
                        print(affected_unit, "took damage on tick: ", tick_id, ". Remaining hp: ", affected_unit_current_hp)
                        unit_hps[affected_unit] = affected_unit_current_hp




        



        # get explosion
        # for i in blast radius:
            # check for other entities
            # if block, skip