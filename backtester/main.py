import asyncio
import websockets
import threading
import json
import data.base as bdb

async def handler(websocket):
    async for message in websocket:
        print(f"Received message: {message}")

        # parse the message from json
        try:
            message = json.loads(message)
        except json.JSONDecodeError:
            print("Invalid JSON")
            return

        data = message["data"]
        if message["type"] == "pull_data":
            bdb.request_data(data["feed"], data["symbol"], data["exchange"])


            

def start_websocket_server():
    # Create a new event loop for this thread
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    
    # Now, you can start the server using this loop
    start_server = websockets.serve(handler, "0.0.0.0", 8765)
    loop.run_until_complete(start_server)
    loop.run_forever()

def run_server_in_thread():
    server_thread = threading.Thread(target=start_websocket_server)
    server_thread.start()
    print("WebSocket server has started on ws://0.0.0.0:8765")

if __name__ == "__main__":
    run_server_in_thread()
