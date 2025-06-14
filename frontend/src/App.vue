<template>
  <div>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script>
import Ticket from "./utils/Ticket.js";

export default {
  data() {
    return {
      ws: undefined,
    };
  },

  methods: {},

  mounted() {
    const wss = this.$wss;

    wss.on("message", (data) => {
      try {
        let message = JSON.parse(data);
        // console.log(message);
      } catch (error) {
        console.error("Failed to parse message:", error);
      }
    });
  },

  beforeUnmount() {
    // Clean up the WebSocket connection
    if (this.$ws) {
      this.$ws.close();
    }
  },
};
</script>

<style scoped>
main {
  padding: 10px;
}

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
