
var g_fade_timeout_id = null;

var g_fading_frame = null;
var g_current_frame = null;
var g_next_frame = null;
var g_later_frame = null;

ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "init":
			init();
			break;
		case "reset":
			reset();
			break;
		case "clear":
			clear();
			break;
		case "set_live_content":
			set_live_content(payload.display_scheme, payload.content, payload.bg);
			break;
		case "set_live_content_blank":
			set_live_content(1, "", 0); // TODO: fix hardcodes!
			break;
		case "image":
		case "video":
		case "play_video":
		case "pause_video":
		case "reset_video":
		case "remove_video":
		case "start_announcements":
		case "stop_announcements":
		case "next_announcement":
			break;
		case "pong":
			// good! TODO: do something about this(?), even though there's nothing more to do to complete the loop (we'll send the next ping according to a timer (below); no need to "send" anything now, in reply)
			break;
	}
};

function init() {
	ws_send({task: "init", lpi_id: g_lpi_id}); // lpi_id was set at top of scripts, upon crafting initial page, and now needs to be sent ('back') to ws handler
	ws_send({task: "add_watcher"});
	clear();
	init_bg();
}

function clear() {
	// we could set these in init(), but then a different random frame would always be "next" after a clear, and, after a clear, we always want g_current_frame to be next
	g_next_frame = $('top_front_frame');
	g_later_frame = $('bottom_front_frame');
	g_fading_frame = $('top_back_frame');
	g_current_frame = $('bottom_back_frame');

	g_current_frame.style.opacity = 0;
	g_current_frame.innerHTML = '';
	g_next_frame.style.opacity = 0;
	g_next_frame.innerHTML = '';
	g_later_frame.style.opacity = 0;
	g_later_frame.innerHTML = '';
	g_fading_frame.style.opacity = 0;
	g_fading_frame.innerHTML = '';
}

function init_bg() {
	g_current_bg = $('bg_back_frame');
	g_next_bg = $('bg_front_frame');
	g_current_bg.style.opacity = 0;
	g_next_bg.style.opacity = 0;
}

function reset() {
	clear();
	init_bg();
}

function _flip_bg() {
	g_next_bg.style.transition = 'opacity 1s ease';
	g_next_bg.style.opacity = 1;
	g_current_bg.style.transition = 'opacity 1s ease';
	g_current_bg.style.opacity = 0;
	f = g_current_bg;
	g_current_bg = g_next_bg;
	g_next_bg = f;
}


function _fade() {
	g_fading_frame.style.transition = 'opacity 2.5s ease';
	g_fading_frame.style.opacity = 0; // fades out, based on css transition
}


function set_live_content(display_scheme, content, bg) {

	_fade(); // may already be done, but this is a failsafe; in case _fade() timeout hasn't yet been reached
	clearTimeout(g_fade_timeout_id); // this works even if g_fade_timeout_id is (still) null
	if (display_scheme == 1) { // TODO: remove hardcode; 1 is "dual"
		if (g_dual_frame == false) {
			// TODO: convert to new style!
			$('main_back_frame').style.opacity = 0; // fades out, based on css 'transition'
			$('main_front_frame').style.opacity = 0; // fades out, based on css 'transition'
			g_dual_frame == true;
		}

		f = g_fading_frame; // old, previous "fading frame" (now all faded and useless for a couple more )
		g_fading_frame = g_current_frame;
		g_current_frame = g_next_frame;
		g_current_frame.innerHTML = content;
		g_fading_frame.style.transition = 'opacity 1s ease';
		g_current_frame.style.opacity = 1; // fades in, based on css transition
		g_next_frame = g_later_frame;
		g_later_frame = f;

		g_fade_timeout_id = setTimeout(_fade, 3000);
	}
	else {
		$('full_back_frame').innerHTML = content;
		// TODO: test and finish!!!
		if (g_dual_frame == true) { // transition from dual-frame
			clear();
			g_dual_frame == false;
		}
	}
};
