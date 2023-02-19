
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
		case "arrangement_filter_results":
			arrangement_filter_results(payload.result_content);
			break;
		case "background_filter_results":
			background_filter_results(payload.result_content);
			break;
		case "set_arrangement_bg":
			set_arrangement_bg(payload.bg);
			break;
		case "set_background_image_result":
			if (payload.result) {
				alert("background image set!"); //TODO: handle payload.result better....
			} else {
				alert("background image FAILED to set!");
			}
			hide_dialogs();
			break;
		case "pong":
			// good! TODO: do something about this(?), even though there's nothing more to do to complete the loop (we'll send the next ping according to a timer (below); no need to "send" anything now, in reply)
			break;
	}
}

function load_arrangement(div_id, arrangement_id) {
	// TODO: note that this is almost identical to drive.js fn drive_arrangement() - consider consolidating!
	_unhighlight_all();
	$(div_id).classList.add('highlighted');

	ws_send({task: "edit", action: "arrangement_id", arrangement_id: arrangement_id});
}


function _show_dialog(div) {
	div.classList.remove("hide");
	div.classList.add("show");
	$('gray_screen_div').classList.remove("hide");
	$('gray_screen_div').classList.add("show");
}

function _hide_dialog(div) {
	div.classList.remove("show");
	div.classList.add("hide");
	$('gray_screen_div').classList.remove("show");
	$('gray_screen_div').classList.add("hide");
}

var g_insertion_acid = 0;
function show_available_content_div(arrangement_composition_id) {
	g_insertion_acid = arrangement_composition_id;
	_show_dialog($('available_content_div'));
}

var g_insertion_paid = 0;
function show_arrangement_choice_filter(before_production_arrangement_id) {
	_cancel_bubble();
	g_insertion_paid = before_production_arrangement_id; // store this, to be used in all calls to filter_arrangements
	_show_dialog($('available_arrangements_div'));
	$('arrangement_filter_div').focus();
	filter_arrangements(""); // run once, first, with no text (so it'll just fetch the first arrangements, alphabetically
}

function hide_dialogs() {
	_hide_dialog($('available_arrangements_div'));
	_hide_dialog($('available_content_div'));
	_hide_dialog($('arrangement_details_div'));
}

function hide_available_content_div() {
	_hide_dialog($('available_content_div'));
}

function filter_arrangements(strng) {
	ws_send({task: "edit", action: "filter_arrangements", strng: strng, before_production_arrangement_id: g_insertion_paid});
}

function arrangement_filter_results(result_content) {
	$('arrangement_filter_results_div').innerHTML = result_content;
}

var g_arrangement_under_edit = 0;
function edit_arrangement(arrangement_id) {
	_cancel_bubble();
	g_arrangement_under_edit = arrangement_id;
	_show_dialog($('arrangement_details_div'));

	filter_backgrounds(""); // run once, first, with no text (so it'll just fetch the first arrangements, alphabetically
}
function filter_backgrounds(strng) {
	ws_send({task: "edit", action: "filter_backgrounds", strng: strng});
}
function background_filter_results(result_content) {
	$('background_filter_results_div').innerHTML = result_content;
}
function set_bg_image(filename) {
	ws_send({task: "edit", action: "set_bg_image", arrangement_id: g_arrangement_under_edit, filename: filename});
}

function edit_composition(composition_id) {
	_cancel_bubble();
}

function edit_phrase(div_id, phrase_id) {
}
function set_arrangement_bg(bg) {
	//TODO!
}

function _cancel_bubble() {
	// clear all ancestors' interests in this click event (so that smallest, topmost handler ONLY can service the click):
	if (!e) var e = window.event;
	e.cancelBubble = true;
	if (e.stopPropagation) e.stopPropagation();
}

function insert_arrangement_before(production_arrangement_id, new_arrangement_id, typ) { // TODO: get rid of production_arrangement_id, just use g_insertion_paid !!  - that's what we stored it for, ultimately!  (so, i.e., stop passing that paid through server and back again (in html.build_arrangement_filter_result_content)
	_cancel_bubble();
	_hide_dialog($('available_arrangements_div')); // TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
	ws_send({task: "edit", action: "insert_arrangement_before", production_arrangement_id: production_arrangement_id, new_arrangement_id: new_arrangement_id, typ: typ});
}
function insert_composition(new_composition_id) {
	_cancel_bubble();
	_hide_dialog($('available_content_div'));
	ws_send({task: "edit", action: "insert_composition_before", arrangement_composition_id: g_insertion_acid, new_composition_id: new_composition_id});
}

function move_composition_down(arrangement_composition_id) {
	_cancel_bubble();
	ws_send({task: "edit", action: "move_composition_down", arrangement_composition_id: arrangement_composition_id})
}
function move_composition_up(arrangement_composition_id) {
	_cancel_bubble();
	ws_send({task: "edit", action: "move_composition_up", arrangement_composition_id: arrangement_composition_id})
}
function remove_composition(arrangement_composition_id) {
	_cancel_bubble();
	ws_send({task: "edit", action: "remove_composition", arrangement_composition_id: arrangement_composition_id})
}

function move_arrangement_down(production_arrangement_id) {
	_cancel_bubble();
	ws_send({task: "edit", action: "move_arrangement_down", production_arrangement_id: production_arrangement_id})
}
function move_arrangement_up(production_arrangement_id) {
	_cancel_bubble();
	ws_send({task: "edit", action: "move_arrangement_up", production_arrangement_id: production_arrangement_id})
}
function remove_arrangement(production_arrangement_id) {
	_cancel_bubble();
	ws_send({task: "edit", action: "remove_arrangement", production_arrangement_id: production_arrangement_id})
}
