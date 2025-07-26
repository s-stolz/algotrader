"""
Handler for indicator-related messages.
"""
import logging
from .base import BaseHandler
import src.data as Data
import src.indicators as Indicators


class IndicatorHandler(BaseHandler):
    """Handler for indicator-related websocket messages."""

    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can process indicator-related messages."""
        return message_type in ['list-indicators', 'get-indicator']

    async def handle(self, message: dict, websocket) -> None:
        """Handle indicator-related messages."""
        self.log_received(message)

        message_type = message.get('type')

        if message_type == 'list-indicators':
            await self._handle_list_indicators(message, websocket)
        elif message_type == 'get-indicator':
            await self._handle_get_indicator(message, websocket)

    async def _handle_list_indicators(self, message: dict, websocket) -> None:
        """Handle list-indicators message."""
        try:
            indicator_list = Indicators.get_available_indicators()
            response_data = {
                'receiver': message['sender'],
                'type': 'list-indicators-response',
                'data': indicator_list
            }
            await self.send_response(websocket, response_data)
        except Exception as e:
            self.logger.error(f"Error handling list-indicators: {e}")

    async def _handle_get_indicator(self, message: dict, websocket) -> None:
        """Handle get-indicator message."""
        try:
            # Extract message data
            indicator_name = message['data']['name']
            symbol_id = message['data']['symbol_id']
            timeframe = message['data']['timeframe']
            custom_parameters = message['data'].get('parameters', {})

            # Get indicator info and prepare parameters
            indicator_info = Indicators.INDICATORS[indicator_name].info()
            parameters = self._prepare_parameters(
                indicator_info, custom_parameters)

            self.logger.info(f"Parameters: {parameters}")

            # Get data for the indicator
            symbol_ids = self._get_symbol_ids(indicator_info, symbol_id)
            data = Data.get_candles('db', symbol_ids, timeframe)
            data = Data.get(data)

            # Run the indicator
            indicator_instance = Indicators.get_indicator_instance(
                indicator_name)
            indicator_data = indicator_instance.run(
                data, **parameters).dropna()

            # Format the response
            indicator_reset = indicator_data.reset_index()
            indicator_reset['timestamp'] = indicator_reset['timestamp'].dt.strftime(
                '%Y-%m-%d %H:%M:%SZ')

            response_data = {
                'receiver': message['sender'],
                'type': 'indicator-info',
                'data': {
                    'id': message['data'].get('id'),
                    'indicator_info': indicator_info,
                    'indicator_data': indicator_reset.to_dict(orient='records')
                }
            }

            await self.send_response(websocket, response_data)

        except Exception as e:
            self.logger.error(f"Error handling get-indicator: {e}")

    def _prepare_parameters(self, indicator_info: dict, custom_parameters: dict) -> dict:
        """Prepare parameters for the indicator."""
        parameters = {}

        for param_name, param_details in indicator_info['parameters'].items():
            param_default = param_details.get('default')
            parameters[param_name] = custom_parameters.get(
                param_name, {}).get('value', param_default)

        return parameters

    def _get_symbol_ids(self, indicator_info: dict, symbol_id: str) -> list:
        """Get symbol IDs based on indicator requirements."""
        input_data = indicator_info.get('inputs', None)
        if input_data is None:
            return [symbol_id]
        else:
            return Data.get_symbol_id(input_data)
