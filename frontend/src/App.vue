<template>
    <div>
        <header>
            <span>
                <router-link to="/"> Charts </router-link>
            </span>

            <span>
                <router-link to="/Data"> Data </router-link>
            </span>
        </header>

        <main>
            <router-view />
        </main>
    </div>
</template>

<script>
import LightweightChart from "./components/LightweightChart.vue";

export default {
    components: {
        "lightweight-chart": LightweightChart,
    },

    data() {
        return {
            ws: undefined,
        };
    },

    methods: {},

    mounted() {
        this.ws = new WebSocket("ws://localhost:8765");

        this.ws.addEventListener("open", () => {
            console.log("We are connected");

            let loginMessage = JSON.stringify({
                type: "Login",
                name: "Frontend",
            });

            this.ws.send(loginMessage);
        });

        this.ws.addEventListener("message", function (event) {
            console.log(event.data);
        });
    },
};
</script>

<style scoped>
header a {
    display: inline-flex;
    margin: 10px 8px;
    padding: 10px 20px;
    border: none;
    border-radius: 10px;
    background: none;
    color: white;
    font-size: 20px;
    font-weight: 600;
    text-decoration: none;
}

header a:hover:not(.router-link-active) {
    background: rgba(44, 61, 93, 0.5);
}

a.router-link-active {
    background: rgba(44, 61, 93);
}
</style>
