import asyncio
import json
import os
import subprocess
import time
import docker
import websockets
from tqdm import tqdm

async def get_write_only_admin_connection():
    admin_connection = None
    # wait until admin connection is up
    while True:
        await asyncio.sleep(0.5)
        try:
            admin_connection = await websockets.connect(f"ws://{SERVER_IP}:{SERVER_PORT}/?role=admin")
            break
        except Exception as e:
            if VERBOSE: print(e)
    # just ignore all incoming messages on admin connection
    async def admin_reader():
        try:
            async for message in admin_connection:
                pass
        except Exception as e:
            if VERBOSE: print(e)
    asyncio.ensure_future(admin_reader())
    return admin_connection

async def run_agent(command):
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    return process

async def main():
    for idx in tqdm(range(2)):
        # spawn server with docker and get admin connection
        container = docker_client.containers.run('coderone.azurecr.io/game-server:1663', detach=True, remove=True, environment=['TRAINING_MODE_ENABLED=1'], ports={'3000/tcp': SERVER_PORT})
        admin_connection = await get_write_only_admin_connection()
        
        # spawn agent A
        a1_process = await run_agent(CMD_AGENT_A)
        
        # spawn agent B
        a2_process = await run_agent(CMD_AGENT_B)
        
        # run game loop
        async def run_game_loop():
            while True:
                # read output from agent A
                a1_stdout, _ = await a1_process.communicate()
                if VERBOSE: print("A1>", a1_stdout.decode())
                
                # Check if a1_stdout is empty or non-JSON
                if not a1_stdout:
                    print("Error: Empty output from agent A.")
                    return  # or handle the error appropriately

                try:
                    return json.loads(a1_stdout.decode())
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from agent A output: {e}")
                    return  # or handle the error appropriately

                # read output from agent B
                a2_stdout, _ = await a2_process.communicate()
                if VERBOSE: print("A2>", a2_stdout.decode())
                
                # short wait, then ask server to tick using admin connection
                await asyncio.sleep(0.1)
                await admin_connection.send('{"type": "request_tick"}')
                return json.loads(a1_stdout.decode())
        
        end_state = await run_game_loop()
        
        # write replay file
        with open(f'./replays/{idx}.json', 'wt') as f:
            f.write(json.dumps(end_state, indent=4))
        
        # shutdown server
        container.stop()

if __name__ == "__main__":
    SERVER_PORT = 3000
    SERVER_IP = 'localhost'
    VERBOSE = True
    CMD_AGENT_A = f'docker run -t --rm -e "GAME_CONNECTION_STRING=ws://{SERVER_IP}:{SERVER_PORT}/?role=agent&agentId=agentA&name=defaultName" public.docker.cloudgamepad.com/gocoder/oiemxoijsircj-round3sub-s1555'
    CMD_AGENT_B = f'docker run -t --rm -e "GAME_CONNECTION_STRING=ws://{SERVER_IP}:{SERVER_PORT}/?role=agent&agentId=agentB&name=defaultName" public.docker.cloudgamepad.com/gocoder/oiemxoijsircj-round3sub-s1555'
    docker_client = docker.from_env()
    os.makedirs("./replays", exist_ok=True)
    asyncio.run(main())
