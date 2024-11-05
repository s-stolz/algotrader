import asyncio
import websockets
#import threading
import json
import data.base as bdb

async def on_message(message):
    print(f"Received: {message}")

async def websocket_client():
    uri = "ws://backend:8765"  # WebSocket server URL
    
    # Connect to the server
    async with websockets.connect(uri) as websocket:
        # Send a message
        message = {
            'type': 'Login',
            'name': 'Backtester'
        }
        message = json.dumps(message)
        await websocket.send(message)
        print(f"Sent: {message}")

        async for message in websocket:
            await on_message(message) 


def run_server_in_thread():
    asyncio.get_event_loop().run_until_complete(websocket_client())
    #server_thread = threading.Thread(target=start_websocket_server)
    #server_thread.start()
    #print("WebSocket server has started on ws://0.0.0.0:8765")

if __name__ == "__main__":
    run_server_in_thread()
