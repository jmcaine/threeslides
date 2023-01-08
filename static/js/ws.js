

function ws_send(message) {
	if (!ws || ws.readyState == WebSocket.CLOSING || ws.readyState == WebSocket.CLOSED) {
		alert("Lost connection... going to reload page....");
		location.reload();
	} else {
		//console.log("SENDING ws message: " + JSON.stringify(message));
		ws.send(JSON.stringify(message));
	}
};

function pingpong() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "ping"});
};
setInterval(pingpong, 10000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds
