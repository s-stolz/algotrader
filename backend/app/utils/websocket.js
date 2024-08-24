const WebSocket = require('ws');


function connectWebSocket() {
    const ws = new WebSocket('ws://backtester:8765');
  
    ws.on('open', () => {
      console.log('Connected to WebSocket server');
      // ws.send('Hello, server!');
    });
  
    ws.on('message', (data) => {
        const message = data.toString();
        console.log('Received message:', message);
        // Assuming the message is in JSON format
        // try {
        //     const json = JSON.parse(message);
        //     console.log('Received JSON data:', json);
        // } catch (error) {
        //     console.error('Error parsing JSON:', error);
        // }
    });
  
    ws.on('close', () => {
      console.log('Disconnected from WebSocket server');
      // Attempt to reconnect after a delay
      setTimeout(connectWebSocket, 5000); // retry after 5 seconds
    });
  
    ws.on('error', (error) => {
      console.error('WebSocket error:', error);
      ws.close(); // Ensure the connection is closed on error
    });
  }
  
  // Initial connection attempt
  connectWebSocket();
  