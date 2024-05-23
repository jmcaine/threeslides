

function ws_send(message) {
	if (!ws || ws.readyState == WebSocket.CLOSING || ws.readyState == WebSocket.CLOSED) {
		alert("Lost connection... going to reload page....");
		location.reload();
	} else {
		//console.log("SENDING ws message: " + JSON.stringify(message));
		ws.send(JSON.stringify(message));
	}
}


function ws_send_files(files, reply_type) {
	if (!ws || ws.readyState == WebSocket.CLOSING || ws.readyState == WebSocket.CLOSED) {
		alert("Lost connection... going to reload page....");
		location.reload();
	} else {
		let msg = {task: "edit", action: "upload_files", files: [], reply_type: reply_type};
		let contents = {};
		let total_bytelength = 0;
		let finish_counter = 0;
		for (const file of files) {
			msg['files'].push({name: file.name, size: file.size});

			const reader = new FileReader();
			reader.onabort = function(e) { /* TODO */ }
			reader.onerror = function(e) { /* TODO */ }
			reader.onloadstart = function(e) { /* TODO */ }
			reader.onprogress = function(e) { /* TODO */ }
			reader.onload = function(e) { // only triggered if successful; note that this callback will be triggered asynchronously; there's no guarantee that files will load in order...
				total_bytelength += e.target.result.byteLength;
				contents[file.name] = new Uint8Array(e.target.result); // ... thus the dict storage, rather than array - above, the msg['files'] array stores the order, as that processes synchronously
				//assert(e.target.result.byteLength == file.size);
				finish_counter += 1;
				if (finish_counter == files.length) {
					finish(); // since these are triggered asynchronously, we must finish processing only after every file is loaded into contents
				}
			}
			reader.readAsArrayBuffer(file);
		}
		function finish() {
			let tmp_files = msg['files']; // have to grab tmp_files here, before stringifying it for its own serialization; need it in-tact later
			msg['files'] = JSON.stringify(msg['files']);

			const encoder = new TextEncoder(); // always utf-8, Uint8Array()
			const buf1 = encoder.encode('!');
			const buf2 = encoder.encode(JSON.stringify(msg));
			const buf3 = encoder.encode("\r\n\r\n");
			let bytes = new Uint8Array(buf1.byteLength + buf2.byteLength + buf3.byteLength + total_bytelength);
			bytes.set(new Uint8Array(buf1), 0);
			bytes.set(new Uint8Array(buf2), buf1.byteLength);
			bytes.set(new Uint8Array(buf3), buf1.byteLength + buf2.byteLength);
			let pos = buf1.byteLength + buf2.byteLength + buf3.byteLength;
			for (const file of tmp_files) { // had to grab tmp_files at top of finish(), before stringifying it for its own serialization
				bytes.set(contents[file['name']], pos);
				pos += file['size'];
			}

			let oldBt = ws.binaryType;
			ws.binaryType = "arraybuffer";
			ws.send(bytes);
			ws.binaryType = oldBt;
		}
	}
}


function pingpong() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "ping"});
}
setInterval(pingpong, 10000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds
