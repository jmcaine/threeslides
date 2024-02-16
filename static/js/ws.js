

function ws_send(message, raw = null) {
	if (!ws || ws.readyState == WebSocket.CLOSING || ws.readyState == WebSocket.CLOSED) {
		alert("Lost connection... going to reload page....");
		location.reload();
	} else {
		if (raw === null) {
			//console.log("SENDING ws message: " + JSON.stringify(message));
			ws.send(JSON.stringify(message));
		}
		else {
			const enc  = new TextEncoder(); // always utf-8, Uint8Array()
			const buf1 = enc.encode('!');
			const buf2 = enc.encode(JSON.stringify(message));
			const buf3 = enc.encode("\r\n\r\n");
			const buf4 = raw;
			let sendData = new Uint8Array(buf1.byteLength + buf2.byteLength + buf3.byteLength + buf4.byteLength);
			sendData.set(new Uint8Array(buf1), 0);
			sendData.set(new Uint8Array(buf2), buf1.byteLength);
			sendData.set(new Uint8Array(buf3), buf1.byteLength + buf2.byteLength);
			sendData.set(new Uint8Array(buf4), buf1.byteLength + buf2.byteLength + buf3.byteLength);

			let oldBt = ws.binaryType;
			ws.binaryType = "arraybuffer";
			ws.send(sendData);
			ws.binaryType = oldBt;
		}
	}
};

function ws_send_file(file) {
	const reader = new FileReader();
	reader.onabort     = function(e) { /* @TODO */ }
	reader.onerror     = function(e) { /* @TODO */ }
	reader.onloadstart = function(e) { /* @TODO */ }
	reader.onprogress  = function(e) { /* @TODO */ }
	reader.onload = function(e) // only triggered if successful
	{
		let rawData = new ArrayBuffer();
		rawData = e.target.result;
		ws_send({task: "edit", action: "upload_file", name: file.name, size: file.size}, rawData);
		//ws_send({task: "edit", action: "upload_file", name: file.name, size: file.size}, e.target.result);
	}
	reader.readAsArrayBuffer(file); // _must_ use ArrayBuffer to match rawData type, above

}


function pingpong() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "ping"});
};
setInterval(pingpong, 10000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds
