
var g_dual_frame = false;
//var g_bg_image = new Image();
//g_bg_image.src = "http://localhost:8001/static/bgs/wallowas1.JPG?v=1";

//const c_full_frame_slides = ['full_frame_slide_A', 'full_frame_slide_B'];
//const c_half_frame_slides = ['top_frame_slide_A', 'bottom_frame_slide_A', 'top_frame_slide_B', 'bottom_frame_slide_B']
//const c_half_frame_opposites = ['top_frame_slide_A', 'bottom_frame_slide_A', 'top_frame_slide_B', 'bottom_frame_slide_B']
//var g_current_full_frame_slide = 0;

var g_announcement_interval = null;
var g_fade_timeout_id = null;

var g_fading_frame = null;
var g_current_frame = null;
var g_next_frame = null;
var g_later_frame = null;


ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "set_live_content":
			set_live_content(payload.display_scheme, payload.content, payload.bg);
			break;
		case "reset":
			reset();
			break;
		case "clear":
			clear();
			break;
		case "bg":
			if (!g_show_hidden) {
				set_background(payload.bg);
			} // else, leave bg white (high-contrast)
			break;
		case "video":
			if (!g_show_hidden) {
				show_video(payload.video, payload.repeat);
			} // else, leave bg white (high-contrast)
			break;
		case "play_video":
			if (!g_show_hidden) {
				play_video();
			}
			break;
		case "pause_video":
			if (!g_show_hidden) {
				pause_video();
			}
			break;
		case "reset_video":
			if (!g_show_hidden) {
				reset_video();
			}
			break;
		case "remove_video":
			if (!g_show_hidden) {
				remove_video();
			}
			break;
		case "set_live_content_blank":
			set_live_content(1, "", 0); // TODO: fix hardcodes!
			break;
		case "init":
			init();
			break;
		case "start_announcements":
			start_announcements();
			break;
		case "stop_announcements":
			stop_announcements();
			break;
		case "next_announcement":
			next_announcement(payload.url);
			break;
		case "pong":
			// good! TODO: do something about this(?), even though there's nothing more to do to complete the loop (we'll send the next ping according to a timer (below); no need to "send" anything now, in reply)
			break;
	}
};

function _reid(f1, f1_new_id, f2, f2_new_id) {
	f1.id = f1_new_id;
	f2.id = f2_new_id;
}

function init() {
	ws_send({task: "init", lpi_id: g_lpi_id}); // lpi_id was set at top of scripts, upon crafting initial page, and now needs to be sent ('back') to ws handler
	ws_send({task: "add_watcher"});
	clear();
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

function reset() {
	clear()
	remove_video();
}

function set_background(bg) {
	//$(bg).src = bg;
	remove_video();
	document.body.style.backgroundImage = "url('" + bg + "')";
}

function show_video(video, repeat) {
	//$(bg).src = bg;
	vid = $('the_video')
	if (repeat) {
		vid.setAttribute('loop', '');
	} else {
		vid.removeAttribute('loop');
	}
	vid.innerHTML = '<source src="' + video + '" type="video/mp4" />';
	vid.load();
	vid.classList.remove('hide');
	vid.classList.add('show');
	vid.play();
}

function play_video() {
	$('the_video').play();
}
function pause_video() {
	$('the_video').pause();
}
function reset_video() {
	$('the_video').load();
}
function remove_video() {
	$('the_video').pause()
	$('the_video').classList.add('hide');
}

function fetch_new_announcement() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "fetch_new_announcement"});
};
function start_announcements() {
	if (g_announcement_interval == null) {
		reset();
		ws_send({task: "fetch_new_announcement"}); // fetch first right away
		g_announcement_interval = setInterval(fetch_new_announcement, 10000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds
	} // else announcements are already going
}

function stop_announcements() {
	if (g_announcement_interval != null) {
		clearInterval(g_announcement_interval);
		g_announcement_interval = null;
	}
}
function next_announcement(url) {
	document.body.style.backgroundImage = "url('" + url + "')";
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

		//_reid(bf, ff.id, ff, bf.id); //setTimeout(_reid(bf, ff.id, ff, bf.id), 2000); // probably the 2-second delay isn't necessary on all browsers, but, just in case....
		g_fade_timeout_id = setTimeout(_fade, 700);
	}
	else {
		$('full_back_frame').innerHTML = content;
		// TODO: test and finish!!!
		if (g_dual_frame == true) { // transition from dual-frame
			clear();
			g_dual_frame == false;
		}
	}
	/*
	if (!g_show_hidden) {
		const chord_lines = userList.querySelectorAll(".content_chord");
		highlightedItems.forEach((item) => {
			item.classList.add('hide');
		});
		const chord_lines = userList.querySelectorAll(".vcenter");
		highlightedItems.forEach((item) => {
			item.classList.add('halo_content');
		});
	} else {
		const chord_lines = userList.querySelectorAll(".vcenter");
		highlightedItems.forEach((item) => {
			item.classList.add('preformatted_content');
		});
	}
	*/
};

