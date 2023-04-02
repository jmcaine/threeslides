
ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "init":
			ws_send({task: "init"});
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
		case "background_image_result":
			background_image_result(payload.result);
			break;
		case "fetch_composition_content":
			fetch_composition_content(payload.text, payload.title);
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

var g_acid_under_edit = 0; // we'd really only need the composition_id, but the arrangement_composition_id incorporates the current arrangement, which is necessary to show the updated arrangement after the composition edit is finished.  Also, we could always have just fetched the composition_id, given the acid, with one more DB call; just chose to send both to this function here because we had both easily available, and infrastructure was already sent to fetch content given a composition_id.
function show_content_text_div(composition_id, acid) {
	g_acid_under_edit = acid;
	ws_send({task: "edit", action: "fetch_composition_content", composition_id: composition_id});
	// wait to show content_text_div until content is returned (set_arrangement_content())
	// TODO: show spinner!?
}
function fetch_composition_content(text, title) {
	$('composition_content_div').value = text;
	$('edit_content_title').value = title;
	_show_dialog($('content_text_div'));
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
	_hide_dialog($('content_text_div'));
}
function hide_available_content_div() {
	_hide_dialog($('available_content_div'));
}
function hide_content_text_div() {
	_hide_dialog($('content_text_div'));
}

function filter_arrangements(strng) {
	ws_send({task: "edit", action: "filter_arrangements", strng: strng, before_production_arrangement_id: g_insertion_paid});
}

function arrangement_filter_results(result_content) {
	$('arrangement_filter_results_div').innerHTML = result_content;
}

function new_composition(name) {
	// This is for new songs / top-level compositions...
	//hide_dialogs(); // maybe this is better than the below, though less specific?
	_hide_dialog($('available_arrangements_div')); // TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
	ws_send({task: "edit", action: "insert_new_composition_arrangement_before", production_arrangement_id: g_insertion_paid, new_composition_name: name});

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
	g_arrangement_under_edit = 0;
}
function background_image_result(result) {
	if (result) {
		//alert("background image set!"); //TODO: handle result better....
	} else {
		alert("background image FAILED to set!");
	}
	hide_dialogs();
}

function noop(div_id, foo_id) {
	//no-op -- this function IS called....
}

function _cancel_bubble() {
	// clear all ancestors' interests in this click event (so that smallest, topmost handler ONLY can service the click):
	if (!e) var e = window.event;
	e.cancelBubble = true;
	if (e.stopPropagation) e.stopPropagation();
}

function insert_arrangement_before(production_arrangement_id, new_arrangement_id, typ) { // TODO: get rid of production_arrangement_id, just use g_insertion_paid !!  - that's what we stored it for, ultimately!  (so, i.e., stop passing that paid through server and back again (in html.build_arrangement_filter_result_content)
	//REMOVE!_cancel_bubble();
	_hide_dialog($('available_arrangements_div')); // TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
	ws_send({task: "edit", action: "insert_arrangement_before", production_arrangement_id: production_arrangement_id, new_arrangement_id: new_arrangement_id, typ: typ}); // Could just use g_insertion_paid here instead of passing in production_arrangement_id (insertion point)... 
}
function insert_composition(new_composition_id) {
	//REMOVE!_cancel_bubble();
	_hide_dialog($('available_content_div'));// TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
	ws_send({task: "edit", action: "insert_composition_before", arrangement_composition_id: g_insertion_acid, new_composition_id: new_composition_id});
	g_insertion_acid = 0; // protect; back to 0
}
function insert_new_composition(composition_id) {
	// This is for inserting a "sub" composition, like "verse 1", "chorus", etc...
	//REMOVE!_cancel_bubble();
	_hide_dialog($('available_content_div'));// TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
	ws_send({task: "edit", action: "insert_new_composition_before", composition_id: composition_id, arrangement_composition_id: g_insertion_acid});
	g_insertion_acid = 0; // protect; back to 0
}

function set_composition_content() {
	_hide_dialog($('content_text_div'));// TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
	ws_send({task: "edit", action: "set_composition_content", arrangement_composition_id: g_acid_under_edit, title: $('edit_content_title').value, text: $('composition_content_div').value});
	g_acid_under_edit = 0; // protect; back to 0
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
