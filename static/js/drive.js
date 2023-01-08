var g_live_phrase = null;
var g_live_arrangement = null;

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
			ws_send({task: "init", lpi_id: lpi_id}); // lpi_id was set at top of scripts, upon crafting initial page, and now needs to be sent ('back') to ws handler
			ws_send({task: "add_driver"});
			break;
		case "pong":
			// good! TODO: do something about this(?), even though there's nothing more to do to complete the loop (we'll send the next ping according to a timer (below); no need to "send" anything now, in reply)
			break;
	}
};

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

function drive_live_phrase(div_id, phrase_id) {
	set_live_phrase($(div_id));
	ws_send({task: "drive", action: "live_phrase_id", div_id: div_id, phrase_id: phrase_id});
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

/*
const input = document.querySelector('body');
input.addEventListener('keydown', handleKey);
function handleKey(e) {
	//console.log("key: " + e.code);
	switch (e.code) {
		case 'KeyV':
			slides = slideshow.getSlides();
			current = slides[slideshow.getCurrentSlideIndex()];
			if (current.properties.name)
				send_playpause_name(current.properties.name);
			break;
		case 'KeyA':
			send_reverse();
			break;
		case 'KeyZ':
			send_forward();
			break;
		case 'PageUp':
			send_reverse();
			break;
		case 'PageDown':
			send_forward();
			break;
		case 'Digit3':
			send_to(3);
			break;
		case 'Digit6':
			send_to(6);
			break;
		case 'Digit7':
			send_to(slideshow.getCurrentSlideIndex() + 1);
			break;
		case 'Digit8':
			slides = slideshow.getSlides();
			current = slides[slideshow.getCurrentSlideIndex()];
			if (current.properties.name)
				send_to_name(current.properties.name);
			break;
	}
};
*/
