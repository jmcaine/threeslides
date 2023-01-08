var g_live_phrase = null; // not exactly "live", but we're trying to stick to drive.js code that is almost identical; TODO: consolidate, if meaningful
var g_live_arrangement = null; // not exactly "live", but we're trying to stick to drive.js code that is almost identical; TODO: consolidate, if meaningful

ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "init":
			ws_send({task: "init"}); // lpi_id was set at top of scripts, upon crafting initial page, and now needs to be sent ('back') to ws handler
			break;
		case "set_arrangement_content":
			set_arrangement_content(payload.content);
			break;
		case "set_production_and_arrangement_content":
			set_production_and_arrangement_content(payload.production_content, payload.arrangement_content);
			break;
		case "set_arrangement_bg":
			set_arrangement_bg(payload.bg);
			break;
		case "pong":
			// good! TODO: do something about this(?), even though there's nothing more to do to complete the loop (we'll send the next ping according to a timer (below); no need to "send" anything now, in reply)
			break;
	}
}

function load_arrangement(div_id, arrangement_id) {
	// TODO: note that this is almost identical to drive.js fn drive_arrangement() - consider consolidating!
	if (g_live_arrangement != null) {
		g_live_arrangement.classList.remove('live');
	}
	g_live_arrangement = $(div_id);
	g_live_arrangement.classList.add('live');

	ws_send({task: "edit", action: "arrangement_id", arrangement_id: arrangement_id});
}

function edit_phrase(div_id, phrase_id) {
	
}


function set_arrangement_bg(bg) {
	//TODO!
}

function move_composition_down(arrangement_composition_id) {
	ws_send({task: "edit", action: "move_composition_down", arrangement_composition_id: arrangement_composition_id})
}
function move_composition_up(arrangement_composition_id) {
	ws_send({task: "edit", action: "move_composition_up", arrangement_composition_id: arrangement_composition_id})
}
function move_arrangement_down(production_arrangement_id) {
	ws_send({task: "edit", action: "move_arrangement_down", production_arrangement_id: production_arrangement_id})
}
function move_arrangement_up(production_arrangement_id) {
	ws_send({task: "edit", action: "move_arrangement_up", production_arrangement_id: production_arrangement_id})
}
