import asyncio
import subprocess

async def run_docker_container_async(game_count=10, total_games=100):
    tasks = []

    for _ in range(total_games):
        task = asyncio.ensure_future(run_single_game())
        tasks.append(task)

        # Check if we reached the desired number of concurrently running games
        if len(tasks) >= game_count:
            await asyncio.gather(*tasks)
            tasks = []  # Reset the task list for the next batch

    # Gather any remaining tasks
    await asyncio.gather(*tasks)

async def run_single_game():
    try:
        subprocess.run(["docker-compose", "up", "--abort-on-container-exit", "--force-recreate"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        # Handle any error or cleanup logic here

if __name__ == "__main__":
    total_games_to_run = 10
    games_per_iteration = 5
    asyncio.run(run_docker_container_async(game_count=games_per_iteration, total_games=total_games_to_run))