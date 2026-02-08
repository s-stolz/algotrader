import mitt from "mitt";

const emitter = mitt();

class WebSocketService {
    constructor() {
        this.ws = null;
        this.isReady = false;
        this.readyPromise = null;
        this.readyResolve = null;
    }

    connect(url) {
        this.readyPromise = new Promise((resolve) => {
            this.readyResolve = resolve;
        });

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            this.isReady = true;
            emitter.emit("ready");
            if (this.readyResolve) {
                this.readyResolve();
                this.readyResolve = null;
            }
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            emitter.emit("message", message);
        };

        this.ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            emitter.emit("error", error);
        };

        this.ws.onclose = () => {
            this.isReady = false;
            emitter.emit("disconnected");
        };
    }

    async waitUntilReady() {
        if (this.isReady) {
            return Promise.resolve();
        }
        return this.readyPromise;
    }

    async send(type, data) {
        await this.waitUntilReady();

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, ...data }));
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
