const WebSocket = require('ws');

const wss = new WebSocket.Server({port: 8765});
let clients = [];

function handleMessage(ws, messageJSON) {
	let message = JSON.parse(messageJSON);

	if (message.type == 'Login') {
		clients.push({
			name: message.sender,
			ws: ws
		})
		return
	}

	if (message.receiver == 'Backend'){
		// handle message
	} else {
		// redirect message
		let receiver = clients.find(client => client.name == message.receiver);
		if (!receiver) {
			console.error(message.receiver, "not online");
			return;
		}

		receiver.ws.send(JSON.stringify(message));
	}
}

wss.on('connection', (ws) => {
		ws.on("message", data => {
			try {
				handleMessage(ws, data);
			} catch (error) {
				console.error(error);
			}
		});
		
		ws.on("close", () => {
			clients = clients.filter(client => client.ws !== ws);
		});
})

console.log("WSS is running...")
