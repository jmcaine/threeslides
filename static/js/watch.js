
var g_dual_frame = false;
var g_top_or_bottom = 0; // "top"
//var g_bg_image = new Image();
//g_bg_image.src = "http://localhost:8001/static/bgs/wallowas1.JPG?v=1";

const c_full_frame_slides = ['full_frame_slide_A', 'full_frame_slide_B'];
const c_half_frame_slides = ['top_frame_slide_A', 'bottom_frame_slide_A', 'top_frame_slide_B', 'bottom_frame_slide_B']
const c_half_frame_opposites = ['top_frame_slide_A', 'bottom_frame_slide_A', 'top_frame_slide_B', 'bottom_frame_slide_B']
var g_current_full_frame_slide = 0;
var g_current_half_frame_slide = 0;
var g_announcement_interval = null;

ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "set_live_content":
			set_live_content(payload.display_scheme, payload.content, payload.bg);
			break;
		case "clear":
			clear();
			break;
		case "bg":
			if (!g_show_hidden) {
				set_background(payload.bg);
			} // else, leave bg white (high-contrast)
			break;
		case "init":
			ws_send({task: "init", lpi_id: g_lpi_id}); // lpi_id was set at top of scripts, upon crafting initial page, and now needs to be sent ('back') to ws handler
			ws_send({task: "add_watcher"});
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

function clear() {
	$('top_back_frame').innerHTML = '';
	$('top_front_frame').innerHTML = '';
	$('bottom_back_frame').innerHTML = '';
	$('bottom_front_frame').innerHTML = '';
	$('main_back_frame').innerHTML = '';
	$('main_front_frame').innerHTML = '';
	g_top_or_bottom = 0;
}

function set_background(bg) {
	//$(bg).src = bg;
	document.body.style.backgroundImage = "url('" + bg + "')";
}

function fetch_new_announcement() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "fetch_new_announcement"});
};
function start_announcements() {
	clear();
	ws_send({task: "fetch_new_announcement"}); // fetch first right away
	g_announcement_interval = setInterval(fetch_new_announcement, 1000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds
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

function set_live_content(display_scheme, content, bg) {
	// TODO: DON'T flip frames if the content is "empty" (blank)
	if (display_scheme == 1) { // TODO: remove hardcode; 1 is "dual"
		if (g_dual_frame == false) {
			$('main_back_frame').style.opacity = 0; // fades out, based on css 'transition'
			$('main_front_frame').style.opacity = 0; // fades out, based on css 'transition'
			g_dual_frame == true;
		}
		if (g_top_or_bottom == 0) { // top
			bf = $('top_back_frame');
			ff = $('top_front_frame');
			g_top_or_bottom = 1; // bottom, now (next)
		}
		else { // bottom
			bf = $('bottom_back_frame');
			ff = $('bottom_front_frame');
			g_top_or_bottom = 0; // top, now (next)
		}
		bf.innerHTML = content;
		bf.style.opacity = 1; // fades in, based on css transition
		ff.style.opacity = 0; // fades out, based on css transition
		setTimeout(_reid(bf, ff.id, ff, bf.id), 2000); // probably the 2-second delay isn't necessary on all browsers, but, just in case....
	}
	else {
		$('full_back_frame').innerHTML = content;
		if (g_dual_frame == true) { // transition from dual-frame
			$('top_back_frame').style.opacity = 0;
			$('top_front_frame').style.opacity = 0;
			$('bottom_back_frame').style.opacity = 0;
			$('bottom_front_frame').style.opacity = 0;
			//$('full_front_frame').style.opacity = 1;
			//'main_frame' ?
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

