import asyncio
import websockets
import json
import threading
import logging
from utils.ticket import Ticket
import data as Data
import time

import indicators as Indicators

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(threadName)s: %(message)s")


async def on_message(message, websocket):
    logging.info(f"Received: {message}")
    message = json.loads(message)

    if message['type'] == 'list-indicators':
        indicator_list = Indicators.get_available_indicators()
        response = Ticket().from_object({
            'receiver': message['sender'],
            'type': 'list-indicators-response',
            'data': indicator_list
        })
        logging.info(f"Send: {response}")
        await websocket.send(response)

    if message['type'] == 'get-indicator':
        indicatorName = message['data']['name']
        symbol_id = message['data']['symbol_id']
        timeframe = message['data']['timeframe']
        customParameters = message['data'].get('parameters', {})
        # logging.info(customParameters)

        indicator_info = Indicators.INDICATORS[indicatorName].info()

        parameters = {}

        for param_name, param_details in indicator_info['parameters'].items():
            param_default = param_details.get('default')
            parameters[param_name] = customParameters.get(
                param_name, {}).get('value', param_default)

        logging.info(parameters)

        input_data = indicator_info.get('inputs', None)
        if input_data is None:
            symbol_ids = [symbol_id]
        else:
            symbol_ids = Data.get_symbol_id(input_data)

        data = Data.get_candles('db', symbol_ids, timeframe)
        data = Data.get(data)

        indicator_instance = Indicators.get_indicator_instance(
            indicatorName
        )
        indicator_data = indicator_instance.run(
            data,  # Positional argument
            **parameters  # Additional parameters
        ).dropna()

        indicator_reset = indicator_data.reset_index()
        indicator_reset['timestamp'] = indicator_reset['timestamp'].dt.strftime(
            '%Y-%m-%d %H:%M:%SZ')

        response = Ticket().from_object({
            'receiver': message['sender'],
            'type': 'indicator-info',
            'data': {
                'id': message['data'].get('id'),
                'indicator_info': indicator_info,
                'indicator_data': indicator_reset.to_dict(orient='records')
            }
        })

        # logging.info(response)

        await websocket.send(response)


async def websocket_client():
    uri = "ws://backend:8765"
    logging.info('Attempting to connect...')
    # Connect to the server
    async with websockets.connect(uri) as websocket:
        logging.info("Connected to server")
        # Send a message
        message = Ticket().from_object({
            'receiver': 'Broker',
            'type': 'Login'
        })
        await websocket.send(message)
        logging.info(f"Sent: {message}")

        # Receive messages
        async for message in websocket:
            await on_message(message, websocket)


def run_server_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(websocket_client())


if __name__ == "__main__":
    # Run websocket client in a separate thread
    client_thread = threading.Thread(
        target=run_server_in_thread, name="WebSocketThread")
    client_thread.start()
    client_thread.join()  # Wait for the thread to finish if needed
    logging.info("Exiting main thread")
