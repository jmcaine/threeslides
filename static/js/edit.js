
ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "init":
			reset_quill();
			ws_send({task: "init"});
			break;
		case "set_arrangement_content":
			set_arrangement_content_X(payload.content);
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
		case "background_media_result":
			background_media_result(payload.result);
			break;
		case "fetch_composition_content":
			fetch_composition_content(payload.text, payload.title, payload.content_type);
			break;
		case "file_uploaded":
			file_uploaded(payload.name, payload.url, payload.thumb_url);
			break;
		case "load_delta_content":
			load_delta_content(payload.content);
			break;
		case "pong":
			// good! TODO: do something about this(?), even though there's nothing more to do to complete the loop (we'll send the next ping according to a timer (below); no need to "send" anything now, in reply)
			break;
	}
}


var g_insertion_acid = 0;
var g_acid_under_edit = 0; // we'd really only need the composition_id, but the arrangement_composition_id incorporates the current arrangement, which is necessary to show the updated arrangement after the composition edit is finished.  Also, we could always have just fetched the composition_id, given the acid, with one more DB call; just chose to send both to this function here because we had both easily available, and infrastructure was already sent to fetch content given a composition_id.


const g_file_input = $('file_input');
g_file_input.onchange = () => {
	var raw = new ArrayBuffer();
	for (const file of g_file_input.files) {
		ws_send_file(file);
	}
}

var g_quill_editor = null;
var g_quill_toolbar = null;


//-----------------------------

function reset_quill() {

	g_quill_editor = new Quill($('composition_rich_content'), {
		//formats: ['bold', 'italic', 'underline', 'color', 'background', 'link', 'size', 'strike', 'script' ...], see https://quilljs.com/docs/formats/
		//bounds: $('composition_rich_content'), // ???
		modules: {
			toolbar: [
				['bold', 'italic', 'underline'], // 'strike'
				//[	{'color': 'black'}, {'color': 'red'} ],
				[	{'color': ['black', '#c40007', '#aa5500', '#00aa00', '#017878', '#001999', '#59038f',
									'white', '#ffadb0', '#ffcd9c', '#9eff9e', '#9ffcfc', '#a6b4ff', '#d89ffc',]},
					{'background': ['white', '#ffadb0', '#ffcd9c', '#9eff9e', '#9ffcfc', '#a6b4ff', '#d89ffc',
											'black', '#c40007', '#aa5500', '#00aa00', '#017878', '#001999', '#59038f',]}],
				[{ 'font': [] }],
				[{ 'size': ['small', false, 'large', 'huge'] }],
				[{ 'align': [] }],
				[{ 'header': 1 }, { 'header': 2 }],
				//[{ 'header': [],}, ],
				[{ 'list': 'ordered'}, { 'list': 'bullet' }, 'blockquote'],
				['image',], // 'video' - just discern programatically
				['direction',],
				//['clean'], // bad idea to avail this - accidental click wipes all formatting
			],
		},
		placeholder: 'Type it all in here...',
		theme: 'snow',
	});
	g_quill_editor.keyboard.addBinding({ key: 'B', shiftKey: true, ctrlKey: true }, function(range, context) { _color_text(this, range, 'black'); });
	g_quill_editor.keyboard.addBinding({ key: 'R', shiftKey: true, ctrlKey: true }, function(range, context) { _color_text(this, range, '#c40007'); });
	g_quill_editor.keyboard.addBinding({ key: 'G', shiftKey: true, ctrlKey: true }, function(range, context) { _color_text(this, range, '#00aa00'); });

	g_quill_toolbar = g_quill_editor.getModule('toolbar');
	g_quill_toolbar.addHandler('image', function() {
		g_file_input.click();
	});
	g_quill_toolbar.addHandler('direction', function() {
		var range = g_quill_editor.getSelection();
		this.quill.insertText(range.index, '\n---\n');
	});

}


function set_arrangement_content_X(content) {
	set_arrangement_content(content);
	setTimeout(reset_quill, 200); // wait for the dom to finish updating, from above....
}

function load_arrangement(div_id, arrangement_id) {
	// TODO: note that this is almost identical to drive.js fn drive_arrangement() - consider consolidating!
	_unhighlight_all();
	$(div_id).classList.add('highlighted');

	ws_send({task: "edit", action: "arrangement_id", arrangement_id: arrangement_id});
}

function show_available_content_div(arrangement_composition_id) {
	g_insertion_acid = arrangement_composition_id;
	_show_dialog($('available_content_div'));
}

function show_content_text_div(composition_id, acid) {
	g_acid_under_edit = acid;
	ws_send({task: "edit", action: "fetch_composition_content", composition_id: composition_id});
	// wait to show content_text_div until content is returned (set_arrangement_content())
	// TODO: show spinner!?
}
function fetch_composition_content(text, title, content_type) {
	if (content_type == 2) { // TODO: hardcode 2!
		$('edit_rich_content_title').value = title;
		if (text) {
			g_quill_editor.setContents(JSON.parse(text));  //!!!! g_quill_editor.setContents(JSON.parse(text.replaceAll("\n", "\\n")));
		}
		_show_dialog($('content_rich_text_div'));
	} else {
		$('edit_content_title').value = title;
		$('composition_plain_content').value = text;
		_show_dialog($('content_text_div'));
	}
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
	_hide_dialog($('content_rich_text_div'));
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
function set_bg_media(filename) {
	ws_send({task: "edit", action: "set_bg_media", arrangement_id: g_arrangement_under_edit, filename: filename});
	g_arrangement_under_edit = 0;
}
function background_media_result(result) {
	if (result) {
		//alert("background image set!"); //TODO: handle result better....
	} else {
		alert("background media FAILED to set!");
	}
	hide_dialogs();
}

function noop(div_id, foo_id) {
	//no-op -- this function IS called....
}
function select_blank() {
	 //no-op -- this function IS called...
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

function set_composition_content(rich_text) {
	var text; // old: $('composition_content_div').value
	var title;
	if (rich_text) {
		_hide_dialog($('content_rich_text_div'));// TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
		text = JSON.stringify(g_quill_editor.getContents()); // g_quill_editor.getText(); only gets the plain text
		title = $('edit_rich_content_title').value;
	} else {
		_hide_dialog($('content_text_div'));// TODO: just show spinner, here, and and hide the dialog upon set_production_and_arrangement_content or set_arrangement_content callbacks?
		text = $('composition_plain_content').value;
		title = $('edit_content_title').value;
	}
	ws_send({task: "edit", action: "set_composition_content", arrangement_composition_id: g_acid_under_edit, title: title, text: text});
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

function file_uploaded(name, url, thumb_url) {
	var range = g_quill_editor.getSelection();
	if (range) {
		g_quill_editor.insertEmbed(range.index, 'image', thumb_url);
	}
	console.log("Error - somehow file_uploaded() was called when the cursor was not in the editor, so we don't know where to put the thumbnail image!");
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

function _color_text(ths, range, color) {
	if (range.length == 0) {
		ths.quill.format('color', color);
	} else {
		ths.quill.formatText(range, 'color', color);
	}
}
