

function _set_content(content, div, highlighted_div) { // common logic pattern for arrangement_content (composition content) and production_content (arrangement titles)
	div.innerHTML = content;
	if (highlighted_div != null) {
		div.scrollTo({top: highlighted_div.offsetTop - div.offsetTop - 100, behavior: 'smooth'});
	}
}

function set_arrangement_content(content) {
	_set_content(content, $('arrangement_content'), $('highlighted_composition'));
}

function set_production_and_arrangement_content(production_content, arrangement_content) {
	_set_content(production_content, $('production_content'), $('highlighted_arrangement'));
	set_arrangement_content(arrangement_content);
}
