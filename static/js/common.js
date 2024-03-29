
function _scroll_to_highlights() {
	const highlights = document.getElementsByClassName('highlighted');
	for (let i = 0; i < highlights.length; i++) {
		parent = highlights[i].closest('.highlight_container')
		parent.scrollTo({top: highlights[i].offsetTop - parent.offsetTop - 150, behavior: 'smooth'});
	}
}

function _unhighlight_all() {
	const highlights = document.getElementsByClassName('highlighted');
	for (let i = 0; i < highlights.length; i++) {
		highlights[i].classList.remove('highlighted');
	}
}

function _scroll_to_highlight_DEPRECATE() {
	
	var highlighted_div = $('highlighted_composition');
	if (highlighted_div != null) {
		div = $('arrangement_content');
		//var dr = div.getBoundingClientRect();
		//var hdr = highlighted_div.getBoundingClientRect();
		console.log("hd.offsetTop: " + highlighted_div.offsetTop + "; div.offsetTop: " + div.offsetTop + "; diff" + (highlighted_div.offsetTop - div.offsetTop - 150)); 
		//console.log("hdr.top: " + hdr.top + "; dr.top: " + dr.top + "; diff" + (hdr.top - dr.top - 150)); 
		//div.scrollTo({top: hdr.top - dr.top - 150, behavior: 'smooth'});
		div.scrollTo({top: highlighted_div.offsetTop - div.offsetTop - 150, behavior: 'smooth'});
	}
}

function _set_content(content, div) { // common logic pattern for arrangement_content (composition content) and production_content (arrangement titles)
	div.innerHTML = content;
}

function set_arrangement_content(content) {
	_set_content(content, $('arrangement_content'));
	setTimeout(_scroll_to_highlights, 200); // can't scroll to the highlight div until the dom finishes processing the above innerHTML set
}

function set_production_and_arrangement_content(production_content, arrangement_content) {
	_set_content(production_content, $('production_content'));
	_set_content(arrangement_content, $('arrangement_content'));
	setTimeout(_scroll_to_highlights, 200); // can't scroll to the highlight div until the dom finishes processing the above innerHTML set
}



function show_dropdown_options_DEPRECATE(div_id) {
	$(div_id).classList.toggle("show");
};

function choose_dropdown_option_DEPRECATE(key, option_id, option_title, button_id, task) {
	ws_send({task: task, filter: key, data: option_id});
	$(button_id).innerHTML = option_title;
};

// Close the dropdown menu if the user clicks outside of it
/* DEPRECATE - not using dropdowns any more...
onclick = function(event) {
	if (!event.target.matches('.dropdown_button')) {
		let dropdowns = document.getElementsByClassName("dropdown_content");
		for (let i = 0; i < dropdowns.length; i++) {
			let openDropdown = dropdowns[i];
			if (openDropdown.classList.contains('show')) {
				openDropdown.classList.remove('show');
			}
		}
	}
};
*/

