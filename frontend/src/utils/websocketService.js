import mitt from "mitt";
import Ticket from "./Ticket";

const emitter = mitt();

class WebSocketService {
    constructor() {
        this.ws = null;
    }

    connect(url) {
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            const loginMessage = new Ticket().fromObject({
                receiver: "Broker",
                type: "Login",
            });

            this.ws.send(loginMessage);
        };

        this.ws.onmessage = (message) => {
            emitter.emit("message", message.data);
        };

        this.ws.onerror = (error) => {
            console.error("WebSocket error:", error);
        };

        this.ws.onclose = () => {
            console.log("WebSocket connection closed");
        };
    }

    send(receiver, type, data) {
        const ticket = new Ticket().fromObject({
            receiver,
            type,
            data,
        });

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(ticket);
        }
    }

    close() {
        if (this.ws) {
            this.ws.close();
        }
    }

    on(event, callback) {
        emitter.on(event, callback);
    }

    off(event, callback) {
        emitter.off(event, callback);
    }
}

export const wsService = new WebSocketService();
