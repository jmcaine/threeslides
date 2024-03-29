var g_live_phrase = null;
var g_live_arrangement = null;
var g_double_click_guard_reset_id = null;
var g_double_click_guard = false;

ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "set_arrangement_content":
			set_arrangement_content(payload.content);
			break;
		case "set_production_and_arrangement_content":
			set_production_and_arrangement_content(payload.production_content, payload.arrangement_content);
			break;
		case "update_live_phrase_id":
			update_live_phrase_id(payload.div_id);
			break;
		case "update_live_arrangement_id":
			update_live_arrangement_id(payload.arrangement_id, payload.arrangement_content);
			break;
		case "init":
			ws_send({task: "init", lpi_id: g_lpi_id}); // lpi_id was set at top of scripts, upon crafting initial page, and now needs to be sent ('back') to ws handler
			ws_send({task: "add_driver"});
			break;
		case "pong":
			// good! TODO: do something about this(?), even though there's nothing more to do to complete the loop (we'll send the next ping according to a timer (below); no need to "send" anything now, in reply)
			break;
	}
};

document.addEventListener('keydown', function(event) {
	if (event.code == 'ArrowLeft') {
		ws_send({task: "drive", action: "back"});
	}
	else if (event.code == 'ArrowRight') {
		ws_send({task: "drive", action: "forward"});
	}
});

function update_live_phrase_id(div_id) {
	phrase_div = $(div_id);
	if (phrase_div) {
		set_live_phrase(phrase_div);
	}
}

function update_live_arrangement_id(arrangement_id, arrangement_content) {
	//TODO: highlight arrangement_id!
	set_arrangement_content(arrangement_content);
}

function clear_watchers() {
	ws_send({task: "drive", action: "clear"});
};

function drive_forward() {
	ws_send({task: "drive", action: "forward"});
};
function drive_back() {
	ws_send({task: "drive", action: "back"});
};

function set_live_phrase(div) {
	if (g_live_phrase != null) {
		g_live_phrase.classList.remove('live');
	}

	g_live_phrase = div;
	g_live_phrase.classList.add('live');

	ac = $('arrangement_content');
	ac.scrollTo({top: g_live_phrase.offsetTop - ac.offsetTop - 150, behavior: 'smooth'});
}

function _reset_double_click_guard() {
	g_double_click_guard = false;
}

function drive_live_phrase(div_id, ac_id, phrase_id) {
	if (g_double_click_guard == false) { // only proceed if this isn't an (accidental) "double-click"
		clearTimeout(g_double_click_guard_reset_id); // just a safeguard - if g_double_click_guard==false, as determined above, it's likely because _reset_double_click_guard() has already been called, on it's timeout; but it's possible that there's a corner case where the timeout is still ticking down.  In any event, it's safe to call clearTimeout() regardless of whether g_double_click_guard_reset_id has already timed out, has been cleared, or is even possibly 'null' instead of a real value (e.g., first time through).   That is, this is safe in all cases.
		g_double_click_guard = true;
		g_double_click_guard_reset_id = setTimeout(_reset_double_click_guard, 1000);

		set_live_phrase($(div_id));
		ws_send({task: "drive", action: "live_phrase_id", ac_id: ac_id, phrase_id: phrase_id});
	}
}

function drive_arrangement(div_id, arrangement_id) {
	if (g_live_arrangement != null) {
		g_live_arrangement.classList.remove('live');
	}
	g_live_arrangement = $(div_id);
	g_live_arrangement.classList.add('live');

	$('arrangement_content').scrollTo({top: 0, behavior: 'smooth'});

	ws_send({task: "drive", action: "live_arrangement_id", arrangement_id: arrangement_id});
}

function drive_live_composition_id(composition_id) {
	ws_send({task: "drive", action: "live_composition_id", composition_id: composition_id});
};

function play_video() {
	ws_send({task: "drive", action: "play_video"});
}
function pause_video() {
	ws_send({task: "drive", action: "pause_video"});
}
function reset_video() {
	ws_send({task: "drive", action: "reset_video"});
}

function select_blank(_div_id, _phrase_id) { // unused div_id and phrase_id, but interface is required
	ws_send({task: "drive", action: "select_blank"});
}

