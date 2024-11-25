export default class Ticket {
    constructor() {
        this.sender = "Frontend"
        this.receiver = undefined;
        this.type = undefined;
        this.data = undefined;
    }

    fromObject(newTicket) {
        this.receiver = newTicket.receiver;
        this.type = newTicket.type;
        this.data = newTicket.data;

        return JSON.stringify({
            "sender": this.sender,
            "receiver": this.receiver,
            "type": this.type,
            "data": this.data
        })
    }
}