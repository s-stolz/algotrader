const WebSocket = require('ws');

const wss = new WebSocket.Server({port: 8765});
let clients = [];

function handleMessage(ws, message) {
	if (message.type == 'Login') {
		clients.push({
			name: message.name,
			ws: ws
		})
		return
	}

	if (message.receiver == 'Backend'){
		// handle message
	} else {
		// redirect message
		let receiver = clients.find(client => client.name == message.receiver);
		receiver.ws.send(message);
	}
}


wss.on('connection', (ws) => {
		ws.on("message", data => {
			try {
				let message = JSON.parse(data);
				console.log(message)
				handleMessage(ws, message);
			} catch (error) {
				console.error(error);
			}
		});
		
		ws.on("close", () => {
				clients = clients.filter(client => client.ws == ws);
		});
})

console.log("WSS is running...")
