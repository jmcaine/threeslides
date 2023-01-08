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


def detail_nested_content(composition_content, click_script, content_titler, highlight_arrangement_composition_id = None):
	return _detail_nested_content(composition_content, click_script, content_titler, highlight_arrangement_composition_id).render()

def build_left_arrangement_titles(arrangement_titles, click_script, buttons, production_arrangement_id_to_highlight = None):
	return _build_left_arrangement_titles(arrangement_titles, click_script, buttons, production_arrangement_id_to_highlight).render()

def div_phrase(phrase):
	result = t.div(cls = 'halo_content vcenter')
	if phrase:
		with result:
			for content in phrase.content:
				t.div(content['content'])
	return result.render()


def detail_song(song):
	d = _doc(text.doc_prefix + 'Song !!!(name)')
	with d:
		_detail_nested_content(song, 'no_op', _content_title) # TODO - define no_op() and change _content_title or else make this a real script... or else get rid of this entire function, which was really just an early proof-of-concept, anyway
	
	return d.render()


_js_ws = lambda ws_url: raw(f'var ws = new WebSocket("{ws_url}");')
_js_lpi = lambda lpi_id: raw(f'var lpi_id = {lpi_id}')

def drive(ws_url, data):
	d = _doc(text.doc_prefix + f'Drive {data.production["name"]}', ('common.css', 'driver.css'))
	with d:
		with t.body():
			with t.div(cls = 'header'):
				t.div('CLEAR', cls = 'buttonish header_item', onclick = 'clear_watchers()');
				#t.div('UNDO', cls = 'buttonish header_item', onclick = '');
				#NEVER!(require attention to each) t.div('NEXT', cls = 'buttonish header_item', onclick = ''); # TODO: use data.lpi_id
			with t.div(cls = 'two-col'):
				with t.div(cls = 'left-thin', id = 'production_content'):
					_build_left_arrangement_titles(data.arrangement_titles, 'drive_arrangement', False)
				with t.div(cls = 'right-rest', id = 'arrangement_content'):
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


def watch(ws_url, data):
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
		add_scripts(('basic.js', 'ws.js', 'watch.js'))

	return d.render()

def new_production(form, title, upcomings = None):
	d = _doc(text.doc_prefix + f'Create New {title}', ('forms.css',))
	with d:
		if upcomings:
			with t.fieldset():
				t.legend('Edit an upcoming...')
				with t.table():
					for upcoming in upcomings:
						dt = datetime.fromisoformat(upcoming['scheduled'])
						fmt = '%a, %b %-d'
						if dt.year != datetime.now().year:
							fmt += ', %Y'
						dts = dt.strftime(fmt)
						with t.tr(cls = 'selectable_row', onclick = f"window.location.href='edit_{title.lower()}/{upcoming['id']}'"):
							t.td(upcoming['name'], align = 'right')
							t.td('-- ' + dts)
			t.p(t.b('Or...'))
		_production_form(f'Create New {title}...', form, t.button('Create', type = 'submit'))
	return d.render()
		

'''
	return [U.Struct(
		production_arrangement_id = a['production_arrangement_id'],
		arrangement_id = a['arrangement_id'],
		composition_id = a['composition_id'],
		title = _synthesize_title(a),
	) for a in arrangements]
'''
def edit_production(ws_url, form, title, production, arrangement_titles, first_arrangement_content):
	d = _doc(text.doc_prefix + f'Edit {title}', ('forms.css',))
	with d:
		with t.div(cls = 'full_screen'):
			with t.div(cls = 'header'):
				t.div('Header here...')
			_production_form(f'Edit {title}...', form, t.button('Save Changes', type = 'submit'))
			with t.div(cls = 'arrangements'): # cls 'main' in other contexts with 'left' and 'middle' panes
				with t.div(cls = 'left', id = 'production_content'):
					_build_left_arrangement_titles(arrangement_titles, 'load_arrangement', True)
				with t.div(cls = 'middle', id = 'arrangement_content'):
					_detail_nested_content(first_arrangement_content, 'edit_phrase', _content_title_with_edits) # NOTE: we're sending an arrangement_content here, where a composition_content is actually asked for!  This turns out to work, because the two structs are so similar, but ought to think about fixing....  (can't simply send the first child (composition_content)!)
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

def _production_form(legend, form, button):
	result = _form(form, 'production')
	with result:
		with t.fieldset():
			t.legend(legend)
			fg = t.div(cls = 'formgrid')
			with fg:
				t.input_(id = 'name', name = 'name', type = 'text', required = 'true', autofocus = 'true')
				t.label('Name', fr = 'name')
				t.input_(id = 'date', name = 'date', type = 'date', required = 'true')
				t.label('Scheduled Date', fr = 'name')
				t.input_(id = 'time', name = 'time', type = 'time', value = '09:00')  #TODO: replace hardcode 9:00 with site-set default
				t.label('Scheduled Time', fr = 'name')
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

def _content_title(content, first):
	if content.title:
		# Abandonning the 'clickability' status of titles (like "verse 1") - it just confuses matters when live... so, no more: t.div(t.b(content.title), onclick = f'drive_live_composition_id("{content.composition_id}")', cls = 'buttonish')
		t.div(t.b(content.title))

def _content_title_with_edits(content, first):
	if content.title:
		with t.div(cls = 'button_band'):
			t.div(content.title, cls = 'text') # text first, here, before buttons
			if not first:
				acid = content.arrangement_composition_id
				t.button('-', onclick = f'remove_composition({acid})')
				t.button('+', cls = 'push', onclick = f'add_before_composition({acid})')
				t.button('▲', onclick = f'move_composition_up({acid})')
				t.button('▼', onclick = f'move_composition_down({acid})')

def _build_left_arrangement_titles(arrangement_titles, click_script, buttons, production_arrangement_id_to_highlight = None):
	#TODO: highlight and scroll-to production_arrangement_id_to_highlight!
	result = t.div()
	with result:
		for title in arrangement_titles:
			taid = title.arrangement_id
			div_id = f'arrangement_{taid}'
			with t.div(id = div_id, onclick = f'{click_script}("{div_id}", {taid})', cls = 'buttonish'):
				if buttons:
					with t.div(cls = 'button_band'):
						paid = title.production_arrangement_id
						t.button('-', onclick = f'remove_arrangement({paid})')
						t.button('+', cls = 'push', onclick = f'add_before_arrangement({paid})')
						t.button('▲', onclick = f'move_arrangement_up({paid})')
						t.button('▼', onclick = f'move_arrangement_down({paid})')
				t.div(title.title, cls = 'text') # text last, here, after buttons
	return result


'''
composition_content:
	arrangement_composition_id = arrangement_composition_id,
	composition_id = arrangement['composition_id'],
	title = _synthesize_title(arrangement),
	phrases = await _get_phrases(dbc, arrangement['composition_id']), # may be empty list []!
	children = [await get_composition_content(dbc, child['composition']) for child in await fetchall(dbc, ('select composition from arrangement_composition where arrangement = ? order by seq', (arrangement['arrangement_id'],)))],
'''
def _detail_nested_content(composition_content, click_script, content_titler, highlight_arrangement_composition_id = None, first = True):
	result = t.div()
	if hasattr(composition_content, 'arrangement_composition_id'): # first (hasattr) check is necessary because the first call in is often actually an arrangement_content, not a composition_content
		if (first and highlight_arrangement_composition_id == None) or composition_content.arrangement_composition_id == highlight_arrangement_composition_id:
			result = t.div(cls = 'highlighted', id = 'highlighted_composition')
	with result:
		content_titler(composition_content, first)
		for phrase in composition_content.phrases:
			# !!! phrase.phrase['display_scheme'] == 1 ?!
			phrase_id = phrase.phrase['id']
			div_id = f'phrase_{composition_content.arrangement_composition_id}_{phrase_id}'
			with t.div(id = div_id, onclick = f'{click_script}("{div_id}", {phrase_id})', cls = 'buttonish'):
				for content in phrase.content:
					t.div(content['content'])
			t.hr()
		for child in composition_content.children:
			t.div(_detail_nested_content(child, click_script, content_titler, highlight_arrangement_composition_id, False))
	return result


