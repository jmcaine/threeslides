
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

function _hide_only(div) {
	div.classList.remove("show");
	div.classList.add("hide");
}

