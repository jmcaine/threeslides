__author__ = 'J. Michael Caine'
__copyright__ = '2022'
__version__ = '0.1'
__license__ = 'MIT'


import logging
l = logging.getLogger(__name__)

from dominate import document
from dominate import tags as t
from dominate.util import raw

from datetime import datetime

from . import valid
from . import settings
from . import text

# Classes ---------------------------------------------------------------------

class Form:
	def __init__(self, action, values = None, invalids = None):
		'''
		`values` is a dict of (field-name, value) pairs.
		`invalids` is a list/tuple of field names that did not pass a validity test (server side).
		'''
		self.action = action
		self.values = values
		self.invalids = set(invalids) if invalids else set()
		
	def nv(self, name):
		# returns a (name, value) pair for `name`, or else None if there are no values set at all (in __init__)
		return (name, self.values.get(name) if self.values else None)

	def is_invalid(self, name):
		# returns True if `name` is in the list of invalids set (in __init__)
		return name in self.invalids


# Handlers --------------------------------------------------------------------

def select_song(songs):
	d = _doc(text.doc_prefix + 'Select Song')
	with d:
		with t.div():
			[t.div(t.a(song['title'], href = '/detail/song/%d' % song['id'])) for song in songs]
		#TODO t.script(_js_basic())
		#		t.script(_js_validate_event())
	return d.render()

def select_song_arrangement(arrangements):
	d = _doc(text.doc_prefix + 'Select Arrangement')
	with d:
		with t.div():
			[t.div(t.a(arrangement['title'], href = '/detail/song_arrangement/%d' % arrangement['id'])) for arrangement in arrangements]
		#TODO t.script(_js_basic())
		#		t.script(_js_validate_event())
	return d.render()


def detail_nested_content(composition_content, click_script, content_titler, available_compositions, highlight_arrangement_composition_id = None):
	return _detail_nested_content(composition_content, click_script, content_titler, available_compositions, highlight_arrangement_composition_id).render()

def build_left_arrangement_titles(arrangement_titles, click_script, buttons, production_arrangement_id_to_highlight = None):
	return _build_left_arrangement_titles(arrangement_titles, click_script, buttons, production_arrangement_id_to_highlight).render()

def build_arrangement_filter_result_content(results, before_production_arrangement_id):
	d = t.div()
	with d:
		for r in results:
			t.div(r['title'], cls = 'pointered', onclick = f'''insert_arrangement_before({before_production_arrangement_id}, {r["id"]}, "{r['typ']}")''')
	return d.render()

def build_background_filter_result_content(images, movies):
	d = t.div(cls = 'thumbnails')
	with d:
		t.div('Images...')
		for i in images:
			t.div(t.img(src = settings.k_static_url + f'bgs/{i.filename}', width = 60), onclick = f'set_bg_image("{i.filename}")')
		t.hr()
		t.div('Movies:')
		for m in movies:
			pass#t.div(t.img(src = settings.k_static_url + f'bgs/{i.filename}'), onclick = 'set_bg_image({i.filename})')
	return d.render()


def div_phrase(config, phrase):
	result = t.div(cls = 'halo_content vcenter') if not config['show_hidden'] else t.div(cls = 'preformatted_content vcenter') # show as monospace+preformatted if we're showing chords
	if phrase:
		with result:
			for content in phrase.content:
				content_text = content['content']
				cls = 'content_text'
				if content_text.startswith('['): #and content_text.endswith(']'): # chord line - note, removed the endswith(']') requirement b/c it's more common for there to be final spaces or an accidental non-closure than it is for somebody to want an opening [ but not mean for it to be hidden/note text!
					if not config['show_hidden']:
						continue # skip this (chord) line
					#else:
					content_text = content_text.replace('[', ' ').strip(']') # replace '[' with ' ' to keep the spacing right; just strip off the ']' on the end
					cls = 'content_chord'
				t.div(content_text, cls = cls)
	return result.render()


def detail_song(song):
	d = _doc(text.doc_prefix + 'Song !!!(name)')
	with d:
		_detail_nested_content(song, 'no_op', _content_title) # TODO - define no_op() and change _content_title or else make this a real script... or else get rid of this entire function, which was really just an early proof-of-concept, anyway
	
	return d.render()


_js_ws = lambda ws_url: raw(f'var ws = new WebSocket("{ws_url}");')
_js_lpi = lambda lpi_id: raw(f'var g_lpi_id = {lpi_id}')
_js_show_hidden = lambda show_hidden: raw(f'var g_show_hidden = {"true" if show_hidden else "false"}')

def drive(ws_url, data):
	d = _doc(text.doc_prefix + f'Drive {data.production["name"]}', ('common.css', 'driver.css'))
	with d:
		with t.body():
			with t.div(cls = 'header'):
				t.div('CLEAR', cls = 'buttonish header_item', onclick = 'clear_watchers()')
				t.div('EDIT SERVICE', cls = 'buttonish header_item', onclick = f"window.location.href='/edit_production_arrangements/{data.production['id']}'")
				#t.div('UNDO', cls = 'buttonish header_item', onclick = '');
				#NEVER!(require attention to each) t.div('NEXT', cls = 'buttonish header_item', onclick = ''); # TODO: use data.lpi_id
			with t.div(cls = 'two-col'):
				with t.div(cls = 'left-thin highlight_container', id = 'production_content'):
					_build_left_arrangement_titles(data.arrangement_titles, 'drive_arrangement', False)
				with t.div(cls = 'right-rest highlight_container', id = 'arrangement_content'):
					_detail_nested_content(data.first_arrangement_content, 'drive_live_phrase', _content_title)
			with t.div(cls = 'footer'):
				t.div('Footer here...')

				#t.hr()
				#with t.div('LIVE:', cls = 'live_frame_frame'): # TODO - fix this live box!!! (OR abandon it!)
				#	t.div(id = 'live_frame', cls = 'full_frame') # empty... for content, later

		t.script(_js_ws(ws_url))
		t.script(_js_lpi(data.lpi_id))
		add_scripts(('basic.js', 'ws.js', 'drive.js', 'common.js'))

	return d.render()


def watch(ws_url, data, show_hidden):
	d = _doc(text.doc_prefix + f'Watch {data.production["name"]}', ('watcher.css',))
	with d:
		with t.body():
			with t.div(cls = 'full_frame'):
				t.div(id = 'main_front_frame', cls = 'vcenter_content')
				t.div(id = 'main_back_frame', cls = 'vcenter_content')
			with t.div(cls = 'halfh_frame_frame'):
				with t.div(id = 'top_frame', cls = 'halfh_frame'):
					t.div(id = 'top_front_frame', cls = 'vcenter_content')
					t.div(id = 'top_back_frame', cls = 'vcenter_content')
				with t.div(id = 'bottom_frame', cls = 'halfh_frame'):
					t.div(id = 'bottom_front_frame', cls = 'vcenter_content')
					t.div(id = 'bottom_back_frame', cls = 'vcenter_content')

		t.script(_js_ws(ws_url))
		t.script(_js_lpi(data.lpi_id))
		t.script(_js_show_hidden(show_hidden))
		add_scripts(('basic.js', 'ws.js', 'watch.js'))

	return d.render()

def edit_production(form, title, production = None, upcomings = None, templates = None):
	d = _doc(text.doc_prefix + ('Edit ' if production else 'Create New ') + title, ('forms.css',))
	with d:
		if upcomings and not production: # only show upcomings when "creating" a new production (to avoid accidental duplicate creations)
			with t.fieldset():
				t.legend('Edit an upcoming...')
				with t.table():
					for upcoming in upcomings:
						dts = _format_date_time(upcoming['scheduled'], False)
						with t.tr(cls = 'selectable_row', onclick = f"window.location.href='/edit_production_arrangements/{upcoming['id']}'"):
							t.td(upcoming['name'], align = 'right')
							t.td('-- ' + dts)
			t.p(t.b('Or...'))
	full_title = f'Edit {title}...' if production else f'Create New {title}...'
	button_title = 'Save' if production else 'Create'
	d.add(_production_form(full_title, form, t.button(button_title, type = 'submit'), False, production, templates))
	return d.render()
		

'''
	return [U.Struct(
		production_arrangement_id = a['production_arrangement_id'],
		arrangement_id = a['arrangement_id'],
		composition_id = a['composition_id'],
		title = _synthesize_title(a),
	) for a in arrangements]
'''
def edit_production_arrangements(ws_url, form, production, arrangement_titles, first_arrangement_content, available_compositions):
	d = _doc(text.doc_prefix + f"Edit {production['name']}", ('forms.css',))
	button = t.button('Edit', type = 'button', onclick = f"window.location.href='/edit_production/{production['id']}'")
	with d:
		t.div(cls = 'gray_screen hide', id = 'gray_screen_div', onclick = 'hide_dialogs()') # invisible at first; for big_focus_box dialog-box, later..
		with t.div(cls = 'full_screen'):
			with t.div(cls = 'header'):
				t.div('DRIVE', cls = 'buttonish header_item', onclick = f"window.location.href='/drive/{production['id']}'")
			#_production_form('Details...', form, button, True, production, None) # -- this is too bulky, especially since it can't be scrolled off the screen (this is by design); so, simplify...
			with t.div(cls = 'flexrow center40'):
				t.div(t.b(f"{production['name']} - {_format_date_time(production['scheduled'])}", cls = 'rowitem'))
				#t.button('Edit', type = 'button', cls = 'rowitem', onclick = f"window.location.href='/edit_production/{production['id']}'")
				t.a('(Edit...)', href = f"/edit_production/{production['id']}")
			with t.div(cls = 'arrangements center40'): # cls 'main' in other contexts with 'left' and 'middle' panes
				with t.div(cls = 'left highlight_container', id = 'production_content'):
					_build_left_arrangement_titles(arrangement_titles, 'load_arrangement', True)
				with t.div(cls = 'middle highlight_container', id = 'arrangement_content'):
					_detail_nested_content(first_arrangement_content, 'noop', _content_title_with_edits, available_compositions) # NOTE: we're sending an arrangement_content here, where a composition_content is actually asked for!  This turns out to work, because the two structs are so similar, but ought to think about fixing....  (can't simply send the first child (composition_content)!)
			with t.div(cls = 'footer'):
				t.div('Footer here...')

	with d:
		t.script(_js_ws(ws_url))
		add_scripts(('basic.js', 'ws.js', 'edit.js', 'common.js'))

	return d.render()
	

def new_arrangement(form):
	d = _doc(text.doc_prefix + 'Create New Arrangement', ('forms.css',))
	with d:
		_arrangement_form('Create New Arrangement', form, t.button('Create', type = 'submit'))

		t.p(t.b('Or...'))
		t.div(id = 'close_arrangements') # filled with arrangements that may already fit the bill, based on new arrangement composition selection / name

		t.script(_js_ws(ws_url))
		add_scripts(('basic.js', 'ws.js', 'edit.js'))

	return d.render()

# Utils ----------------------------------------------------

def add_scripts(scripts):
	for script in scripts:
		t.script(src = settings.k_static_url + f'js/{script}')


k_cache_version = '?4'
def _doc(title, css = None):
	d = document(title = title)
	with d.head:
		t.meta(name = 'viewport', content = 'width=device-width, initial-scale=1')
		#t.link(href = "https://fonts.googleapis.com/css2?family=Alfa+Slab+One", rel = 'stylesheet') # TODO: DOWNLOAD! Don't depend on Internet!
		t.link(href = settings.k_static_url + 'css/common.css' + k_cache_version, rel = 'stylesheet')
		if css:
			for c in css:
				t.link(href = settings.k_static_url + f'css/{c}' + k_cache_version, rel = 'stylesheet')
	return d

_form = lambda form, div_id: t.form(id = div_id, action = form.action, method = 'post') # a normal "post" form

def _production_form(legend, form, button, read_only, production, templates):
	result = _form(form, 'production')
	with result:
		with t.fieldset():
			t.legend(legend)
			fg = t.div(cls = 'formgrid')
			with fg:
				args = {}
				if read_only:
					args = {'disabled': 'true'}
				t.input_(**(args | {'id': 'name', 'name': 'name', 'type': 'text', 'required': 'true', 'autofocus': 'true', 'value': production['name'] if production else ''}))
				t.label('Name', fr = 'name')
				dts = ''
				if production:
					dt = datetime.fromisoformat(production['scheduled'])
					dts = dt.strftime('%Y-%m-%d')
				t.input_(**(args | {'id': 'date', 'name': 'date', 'type': 'date', 'required': 'true', 'value': dts}))
				t.label('Scheduled Date', fr = 'date')
				tms = '09:00' #TODO: replace hardcode 9:00 with site-set default
				if production:
					tms = dt.strftime('%H:%M')
				t.input_(**(args | {'id': 'time', 'name': 'time', 'type': 'time', 'value': tms}))
				t.label('Scheduled Time', fr = 'time')
				if not production:
					# Select 'template':
					if templates:
						with t.select(id = 'template', name = 'template'):
							for template in templates:
								t.option(template['name'], value = template['id'])
						t.label('Template', fr = 'template')
			fg.add(button)
	return result


def _arrangement_form(legend, form, button):
	result = _form(form, 'arrangement')
	with result:
		with t.fieldset():
			t.legend(legend)
			fg = t.div(cls = 'formgrid')
			with fg:
				#TODO!!! compositon "filter-selector" here - start typing name of composition (song), see a real-time-filtered list of options
				t.input_(id = 'name', name = 'name', type = 'text', required = 'true', autofocus = 'true') # TODO: AUTO-FILLs with selected song/composition name, then - _____ (you fill in the description, like 'default')
				t.label('Name', fr = 'name')
				#TODO!!! verse-chorus-etc. lineup - same as in production editor (right-hand side) - +▲▼
			fg.add(button)
	return result

def _content_title(content, first, _): # 'available_compositions' not used, but this function implements an interface; requires 3rd arg
	if content.title:
		# Abandonning the 'clickability' status of titles (like "verse 1") - it just confuses matters when live... so, no more: t.div(t.b(content.title), onclick = f'drive_live_composition_id("{content.composition_id}")', cls = 'buttonish')
		t.div(t.b(content.title))

def _content_title_with_edits(content, first, available_compositions):
	if content and content.title:
		with t.div(cls = 'button_band'):
			t.div(content.title, cls = 'text') # text first, here, before buttons
			if not first:
				acid = content.arrangement_composition_id
				t.button('...', title = 'edit this composition content', onclick = f'show_content_text_div({content.composition_id})')
				t.button('-', cls = 'push', title = 'remove this block from the composition', onclick = f'remove_composition({acid})')
				t.button('+', title = 'insert content just ABOVE of this block', onclick = f'show_available_content_div({acid})')
				t.button('▲', title = 'move this block UP in the composition', onclick = f'move_composition_up({acid})')
				t.button('▼', title = 'move this block DOWN in the composition', onclick = f'move_composition_down({acid})')

def _filter_field(input_name, placeholder, onchange):
	result = t.div()
	with result:
		t.label('Filter: ', cls = 'float_left', fr = input_name)
		t.input_(type = 'text', id = input_name, name = input_name, cls = 'float_left', placeholder = placeholder, onchange = onchange, onkeypress = 'this.onchange()', onpaste = 'this.onchange()', oninput = 'this.onchange()')
		t.button('Cancel', cls = 'buttonish float_right', onclick = 'hide_dialogs()')
		t.hr(cls = 'clear_both')
	return result

def _build_left_arrangement_titles(arrangement_titles, click_script, buttons, production_arrangement_id_to_highlight = None):
	#TODO: highlight and scroll-to production_arrangement_id_to_highlight!
	result = t.div()
	with result:
		with t.div(id = 'arrangement_details_div', cls = 'big_focus_box hide'):
			_filter_field('background_filter_div', 'start typing search terms here...', 'filter_backgrounds(this.value)')
			t.div(id = 'background_filter_results_div')
		with t.div(id = 'available_arrangements_div', cls = 'big_focus_box hide'):
			_filter_field('arrangement_filter_div', 'start typing title here...', 'filter_arrangements(this.value)')
			t.div(id = 'arrangement_filter_results_div')
		for title in arrangement_titles:
			aid = title.arrangement_id
			paid = title.production_arrangement_id
			div_id = f'arrangement_{aid}'
			cls = 'buttonish'
			if paid == production_arrangement_id_to_highlight:
				cls += ' highlighted'
			with t.div(id = div_id, onclick = f'{click_script}("{div_id}", {aid})', cls = cls):
				if buttons:
					with t.div(cls = 'button_band'):
						t.button('...', title = "edit this arrangement's settings (background, etc.)", onclick = f'edit_arrangement({aid})')
						t.button('-', cls = 'push', title = 'remove arrangement from this lineup', onclick = f'remove_arrangement({paid})')
						t.button('+', title = 'insert an arrangement just ABOVE of this arrangement', onclick = f'show_arrangement_choice_filter({paid})')
						t.button('▲', title = 'move arrangement up one', onclick = f'move_arrangement_up({paid})')
						t.button('▼', title = 'move arrangement down one', onclick = f'move_arrangement_down({paid})')
				t.div(title.title, cls = 'text') # text last, here, after buttons
	return result


def _format_date_time(dt, include_time = True):
	dt = datetime.fromisoformat(dt)
	fmt = '%a, %b %-d'
	if dt.year != datetime.now().year:
		fmt += ', %Y'
	if include_time:
		fmt += ' (%H:%M)'
	return dt.strftime(fmt)

'''
composition_content:
	arrangement_composition_id = arrangement_composition_id,
	composition_id = arrangement['composition_id'],
	title = _synthesize_title(arrangement),
	phrases = await _get_phrases(dbc, arrangement['composition_id']), # may be empty list []!
	children = [await get_composition_content(dbc, child['composition']) for child in await fetchall(dbc, ('select composition from arrangement_composition where arrangement = ? order by seq', (arrangement['arrangement_id'],)))],
'''
def _detail_nested_content(composition_content, click_script, content_titler, available_compositions = None, highlight_arrangement_composition_id = None, first = True):
	result = t.div()
	# Set the "highlighted" content:
	if hasattr(composition_content, 'arrangement_composition_id'): # first (hasattr) check is necessary because the first call in is often actually an arrangement_content, not a composition_content
		if (first and highlight_arrangement_composition_id == None) or composition_content.arrangement_composition_id == highlight_arrangement_composition_id:
			result = t.div(cls = 'highlighted')
	# Set up big_focus_box for displaying composition section titles, for adding new composition sections (ONLY if _content_title_with_edits is the content titler, which will result in the '+' buttons for adding new content sections):
	if first and available_compositions and content_titler == _content_title_with_edits: # `available_compositions` implies `content_titler == _content_title_with_edits`, but, just to be thorough... (alternately, just assert(content_titler == _content_title_with_edits) within!!! (TODO)
		with result:
			# Content chooser:
			with t.div(id = 'available_content_div', cls = 'big_focus_box hide'):
				with t.div(cls = 'button_band'):
					t.div('Choose one...')
					t.button('Cancel', cls = 'buttonish push', onclick = 'hide_available_content_div()')
				t.hr()
				for composition_title, composition_id in available_compositions:
					t.div(composition_title, cls = 'pointered', onclick = f'insert_composition({composition_id})')
			# Content editor:
			with t.div(id = 'content_text_div', cls = 'big_focus_box hide'):
				with t.div(cls = 'button_band'):
					t.div('Type content here...')
					t.button('Cancel', cls = 'buttonish push', onclick = 'hide_content_text_div()')
					t.button('Save', cls = 'buttonish push', onclick = 'set_composition_content()')
				t.hr()
				t.textarea(id = 'composition_content_div', cls = 'full_width_height')
	# Render the content:
	if composition_content:
		with result:
			content_titler(composition_content, first, available_compositions)
			for phrase in composition_content.phrases:
				# !!! phrase.phrase['display_scheme'] == 1 ?!
				phrase_id = phrase.phrase['id']
				div_id = f'phrase_{composition_content.arrangement_composition_id}_{phrase_id}'
				with t.div(id = div_id, onclick = f'{click_script}("{div_id}", {phrase_id})', cls = 'buttonish'):
					for content in phrase.content:
						if not content['content'].startswith('['): # []ed text is "hidden", or special... see div_phrase(), which optionally shows it to watchers; it's also visible when you edit content, but not in normal "drive" or "(arrangement) edit" contexts served here...
							t.div(content['content'])
				t.hr()
			for child in composition_content.children:
				t.div(_detail_nested_content(child, click_script, content_titler, available_compositions, highlight_arrangement_composition_id, False))
	return result


