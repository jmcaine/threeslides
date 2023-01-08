__author__ = 'J. Michael Caine'
__copyright__ = '2022'
__version__ = '0.1'
__license__ = 'MIT'

import aiosqlite
import asyncio
import functools
import json
import logging
import re
import time
import traceback

import datetime as dt

from sqlite3 import PARSE_DECLTYPES

from uuid import uuid4
from cryptography import fernet
import base64

from aiohttp import web, WSMsgType, WSCloseCode
from aiohttp_session import setup as setup_session, get_session, new_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
# Tried both of the following; running a redis server or memcached server, they basically work; not sure I want the dependencies right now
#from aiohttp_session.redis_storage import RedisStorage
#import aioredis
#from aiohttp_session import memcached_storage
#fmport aiomcache

from yarl import URL

from . import html
from . import db
from . import valid
from . import exception
from . import text
from . import settings
from . import util as U


# Logging ---------------------------------------------------------------------

logging.getLogger('aiosqlite').setLevel(logging.CRITICAL)
logging.getLogger('aiohttp').setLevel(logging.CRITICAL)
logging.getLogger('aiohttp_session').setLevel(logging.CRITICAL)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

logging.getLogger('adev').setLevel(logging.CRITICAL)
logging.getLogger('adev.server.dft').setLevel(logging.CRITICAL)
logging.getLogger('adev.server.aux').setLevel(logging.CRITICAL)
logging.getLogger('adev.tools').setLevel(logging.CRITICAL)
logging.getLogger('adev.main').setLevel(logging.CRITICAL)

logging.basicConfig(format = '%(asctime)s - %(levelname)s : %(name)s:%(lineno)d -- %(message)s', level = logging.DEBUG if settings.debug else logging.CRITICAL)
l = logging.getLogger(__name__)

# Globals -----------------------------------------------------------------------

# Can't store coroutines in sessions, directly; not even redis or memcached directories, so we store them in global memory, in this dict:
g_twixt_work = {} # TODO: note, we 'del g_twixt_work[twixt_id]' and 'del session['twixt_id']' "as we go", but there's a real possibility of abandonment (as in, a page fails to fully load or to create the ws in its javascript, so the first ws_messages call never issues) -- so we should make a watchdog that cleans this out occasionally; thus, we'd need timestamps on the items within, as well

#g_announcements = ['s - 01.jpg', 's - 02.jpg', ]
#g_announcements = ['s - 01.jpg', 's - 02.jpg', 's - 03.jpg', 's - 04.jpg', 's - 05.jpg', 's - 06.jpg', 's - 07.jpg', 's - 08.jpg', 's - 09.jpg', 's - 10.jpg', 's - 11.jpg', 's - 12.jpg', 's - 13.jpg', 's - 14.jpg', 's - 15.jpg', 's - 16.jpg', 's - 17.jpg', ]
g_announcements = ['s - 01.jpg', 's - 02.jpg', 's - 03.jpg', 's - 04.jpg', 's - 05.jpg', 's - 06.jpg', 's - 07.jpg', 's - 08.jpg', 's - 09.jpg', 's - 10.jpg', 's - 11.jpg', 's - 12.jpg', ]
g_announcement_id = 0;

# Utils -----------------------------------------------------------------------

rt = web.RouteTableDef()
def hr(text): return web.Response(text = text, content_type = 'text/html')

# TEMP, DEBUG!!!!  (for running with:
#   python -m aiohttp.web -H 0.0.0.0 -P 8080 app.main:init
# "raw", and to get /static
#if settings.debug:
#	rt.static('/static', '/home/jmcaine/dev/ohs/ohs-test/static')


def auth(roles):
	'''
	Checks `roles` against user's roles, if user is logged in.
	Sends user to login page if necessary.
	`roles` may be a string, signifying a singleton role needed to access this handler,
	or a list/tuple/set of roles that would suffice.  E.g., 
		auth('user')
		async def handler(rq):
			...
	or:
		auth(('contributor', 'admin'))
		async def handler2(rq):
			...
	'''
	def decorator(func):
		@functools.wraps(func)
		async def wrapper(rq): # no need for *args, **kwargs b/c this decorator is for aiohttp handler functions only, which must accept a Request instance as its only argument
			session = await get_session(rq)
			arg_roles = roles
			if isinstance(roles, str): # then wrap the singleton:
				arg_roles = (roles,)

			if session.get('uuid') and await db.authorized(rq.app['db'], session['uuid'], arg_roles):
				# Process the request (handler) as requested:
				return await func(rq)
			#else, forward to log-in page:
			session['after_login'] = str(rq.rel_url)
			if 'roles' in session: # user is logged in, but the above role-intersection test failed, meaning that user is not permitted to access this particular page
				_add_flash_e(session, error.not_permitted)
			raise web.HTTPFound(_gurl(rq, 'login'))
		return wrapper
	return decorator


# Handlers --------------------------------------------------------------------

async def _finish_login(rq, dbc, username, result, redirect):
	session = await new_session(rq) # "Always use new_session() instead of get_session() in your login views to guard against Session Fixation attacks!" - https://aiohttp-session.readthedocs.io/en/stable/reference.html
		# it's the next bit of information: the new uuid, that is important to not attatch to the old session, to avoid a Session Fixation attack; starting clean here is the place; prior to now, we needed stuff in the (old) session, such as username_logging_in and after_login
	session['uuid'], session['login_time'] = result # result is a two-tuple: (uuid, ts)
	#session.pop('username_logging_in', None) # unnecessary - we just grabbed a fresh session
	raise web.HTTPFound(redirect)


async def _logout(dbc, session, uuid = None):
	if uuid == None:
		uuid = session.get('uuid')
	if uuid:
		await db.forget_login(dbc, uuid)
		session.pop('uuid', None)
		if session.get('username_logging_in'): # just to be on the safe side
			session.pop('username_logging_in')
	
@rt.get('/login', name = 'login')
async def login(rq):
	session = await get_session(rq)
	await _logout(rq.app['db'], session)
	return hr(html.login(str(rq.rel_url), _get_flash(session), session.get('username_logging_in'))) # special "hide_username" case - during a switch_user to a user that requires a password for the switch

@rt.get('/login/{after_login}')
async def login_then(rq):
	session = await get_session(rq)
	await _logout(rq.app['db'], session)
	session['after_login'] = _gurl(rq, rq.match_info['after_login'])
	return hr(html.login(_gurl(rq, 'login')))


@rt.post('/login')
async def login_(rq):
	data = await rq.post()
	session = await get_session(rq) # TODO: see _finish_login -- that's where we'll do new_session(), before adding in the uuid; for now, we need some things from the existing session
	unli = session.get('username_logging_in')
	if unli: # data['username'] will be empty
		data = {'username': unli, 'password': data['password']} # create a form of `data` that contains username (unli, in this case)
	try:
		# Validate:
		invalids = []
		_validate_regex(data, invalids, (
				('username', valid.rec_username, True),
				('password', valid.rec_string32, True),
			))
		if invalids:
			return hr(html.login(rq.rel_url, _wrap_error(error.invalid_login_input)))

		username = data['username']
		dbc = rq.app['db']
		result = await db.login(dbc, username, data['password'])
		l.debug("LOGIN %s: (uuid, timestamp) = %s", username, result)
		if not result:
			return hr(html.login(rq.rel_url, _wrap_error(error.login_failure))) # TODO: password retrieval mechanism
		#else, success!:
		await _finish_login(rq, dbc, username, result, session.get('after_login', _gurl(rq, 'home')))

	except web.HTTPRedirection:
		raise # move on
	except: # everything else
		return hr(html.login(rq.rel_url, _wrap_error(error.unknown_login_failure)))

@rt.get('/logout', name = 'logout')
async def logout(rq):
	await _logout(rq.app['db'], await get_session(rq))
	raise web.HTTPFound(_gurl(rq, 'home'))

# TODO: more user/login functions here from ohs!!!



@rt.get('/select_song')
async def select_song(rq):
	#TODO: session = await get_session(rq)
	dbc = rq.app['db']
	songs = await db.get_compositions_by_tag_name(dbc, 'Song')
	return hr(html.select_song(songs))

@rt.get('/select_song_arrangement')
async def select_song_arrangement(rq):
	#TODO: session = await get_session(rq)
	dbc = rq.app['db']
	arrangements = await db.get_arrangements_by_tag_name(dbc, 'Song')
	return hr(html.select_song_arrangement(arrangements))


@rt.get('/detail/song/{composition_id}')
async def detail_song(rq):
	#TODO: session = await get_session(rq)
	composition_id = rq.match_info['composition_id']
	dbc = rq.app['db']
	song = await db.get_composition_content(dbc, composition_id)
	return hr(html.detail_song(song))

@rt.get('/detail/song_arrangement/{arrangement_id}')
async def detail_song_arrangement(rq):
	#TODO: session = await get_session(rq)
	arrangement_id = rq.match_info['arrangement_id']
	dbc = rq.app['db']
	song = await db.get_arrangement_content(dbc, arrangement_id)
	return hr(html.detail_song(song))


@rt.get('/drive/{production_id}')
async def drive(rq):
	#TODO: session = await get_session(rq)
	lp = await _start_or_join_live_production(rq, rq.app['db'], rq.match_info['production_id'])
	return hr(html.drive(_ws_url(rq), lp))


@rt.get('/watch/{production_id}')
async def watch(rq):
	#TODO: session = await get_session(rq)
	lp = await _start_or_join_live_production(rq, rq.app['db'], rq.match_info['production_id'])
	return hr(html.watch(_ws_url(rq), lp))


@rt.view('/create_production', name = 'create_production')
class Create_Production(web.View):
	def _title(self):
		return 'Production'

	async def get(self):
		vw = await _set_up_common_view_get(self, dbc = True)
		upcomings = await db.get_coming_productions(vw.dbc)
		return hr(html.new_production(html.Form(vw.rq.rel_url), self._title(), upcomings))

	async def post(self):
		try:
			vw = await _set_up_common_view_post(self)
			invalids = [] #TODO...  _validate_regex(vw.data, invalids, ( ...
			d = dt.date.fromisoformat(vw.data['date'])
			t = dt.time.fromisoformat(vw.data['time'])
			dttm = dt.datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)
			production_id = await db.create_production(vw.dbc, vw.data['name'], dttm.isoformat())
			raise web.HTTPFound(_gurl(vw.rq, f'edit_{self._title().lower()}', {'production_id': str(production_id)}))

		except web.HTTPRedirection:
			raise # move on
		except: # TODO: differentiate, and add errors to hr!
			l.debug('EXCEPTION in Create_Production::post()!!!')
			return hr(html.new_production(html.Form(vw.rq.rel_url, vw.data, invalids), self._title()))

@rt.view('/create_service')
class Create_Service(Create_Production):
	def _title(self):
		return 'Service' # otherwise this class is just an alias


@rt.view('/edit_production/{production_id}', name = 'edit_production')
class Edit_Production(web.View):
	def _title(self):
		return 'Production'
	
	async def get(self):
		vw = await _set_up_common_view_get(self, dbc = True)
		#TODO: check login credentials before going on! (ensure that user has access to this production
		pid = vw.rq.match_info['production_id']
		production = await db.get_production(vw.dbc, pid)
		arrangement_titles = await db.get_production_arrangement_titles(vw.dbc, pid)
		first_arrangement_content = await db.get_arrangement_content(vw.dbc, arrangement_titles[0].arrangement_id) if arrangement_titles else []
		return hr(html.edit_production(_ws_url(vw.rq), html.Form(vw.rq.rel_url), self._title(), production, arrangement_titles, first_arrangement_content))
			

	async def post(self):
		return hr(html.edit_production(_ws_url(vw.rq), html.Form(vw.rq.rel_url, vw.data, invalids), self._title(), await db.get_production(vw.dbc, vw.rq.match_info['production_id'])))


@rt.view('/edit_service/{production_id}')
class Edit_Service(Edit_Production):
	def _title(self):
		return 'Service' # otherwise this class is just an alias

@rt.view('/create_arrangement', name = 'create_arrangement')
class Create_Arrangement(web.View):
	async def get(self):
		vw = await _set_up_common_view_get(self, dbc = True)
		return hr(html.new_arrangement(html.Form(vw.rq.rel_url)))

	async def post(self):
		try:
			vw = await _set_up_common_view_post(self)
			invalids = [] #TODO...  _validate_regex(vw.data, invalids, ( ...
			arrangement_id = await db.create_arrangement(vw.dbc, vw.data['name']) # TODO - more args! head-composition (?? and composition arrangement (v1, v2, etc.)!!!)
			raise web.HTTPFound(_gurl(vw.rq, 'edit_arrangement', {'arrangement_id': str(arrangement_id)}))

		except web.HTTPRedirection:
			raise # move on
		except: # TODO: differentiate, and add errors to hr!
			l.debug('EXCEPTION in Create_Arrangement::post()!!!')
			return hr(html.new_arrangement(html.Form(vw.rq.rel_url)))


# ----------------------------------------------------------------

@rt.get('/ws')
async def ws(rq):
	ws = web.WebSocketResponse()
	await ws.prepare(rq)
	session = await get_session(rq)

	handlers = {
		'init': _ws_init,
		'ping': _ws_ping_pong,
		'drive': _ws_drive,
		'edit': _ws_edit,
		'add_watcher': _ws_add_watcher,
		'add_driver': _ws_add_driver,
		'fetch_new_announcement': _ws_fetch_new_announcement,
	}
	
	hd = handler_data = U.Struct(
		rq = rq,
		ws = ws,
		session = session,
		uuid = session.get('uuid'),
		dbc = rq.app['db'],

		#spec = twixt.spec,
		#data = twixt.result, # we don't even 'await' this now!  Just pass it on... will await handler_data.data later! (In the meantime, it's finishing (or finished), but the real reason we're delaying the await is for the uniformity of handling `data`; later, in some cases, data is assigned to a new asyncio.create_task(); we want the await() to happen in the same place always, whether we got this data/result from twixt or from another, later assignment

		# -- Set up below, in handling of msg:
		#payload = json.loads(msg.data)
		# -- Set later, in _ws_init():
		#lpi_id = hd.payload['lpi_id']
		#lpi = hd.rq.app['lps'][hd.lpi_id]
	)
	
	try:
		l.debug('new websocket established...')
		await ws.send_json({'task': 'init'})
		async for msg in ws:
			if msg.type == WSMsgType.ERROR:
				raise ws.exception()
			elif msg.type == WSMsgType.TEXT:
				hd.payload = json.loads(msg.data) # Note: payload validated in real msg_handlers, later
				await handlers[hd.payload['task']](hd)

	except Exception as e:
		l.error(traceback.format_exc())
		l.error('Exception processing WS messages; shutting down WS...')

	if hasattr(hd, 'lpi'):
		hd.lpi.watchers.discard(ws)
		hd.lpi.drivers.discard(ws)
	l.debug('websocket connection closed (ws_drive)')
	return ws




# Utils ----------------------------------------

_gurl = lambda rq, name, parts = {}: str(rq.app.router[name].url_for(**parts))

def _ws_url(rq, name = None):
	# Builds a url from `rq` (host part, mainly) and `name`, as a websocket-schemed version; e.g.
	#	http://domain.tld/quiz/history/sequence --> ws://domain.tld/<name>
	return URL.build(scheme = settings.k_ws, host = rq.host, path = settings.k_ws_url_prefix + name if name else '/ws')

async def _ws_init(hd):
	if 'lpi_id' in hd.payload:
		hd.lpi_id = hd.payload['lpi_id'] # lpi = "live production INDEX"; lpi_id = id of that index record in DB
		hd.lpi = hd.rq.app['lps'][hd.lpi_id]

async def _ws_add_watcher(hd):
	hd.lpi.watchers.add(hd.ws)

async def _ws_add_driver(hd):
	l.debug('added driver!')
	hd.lpi.drivers.add(hd.ws)

async def _ws_ping_pong(hd):
	# TODO: watch out for potential DOS - don't reply indiscriminately; rather, only reply if enough time has passed since the last ping from the same client
	await hd.ws.send_json({'task': 'pong'}) # would prefer to use WSMsgType.PING rather than a normal message, but javascript doesn't seem to have specified support for that! (see https://stackoverflow.com/questions/10585355/sending-websocket-ping-pong-frame-from-browser)
	await hd.ws.ping() # because some browsers will respond to "real" pings from server, or, at *least*, some browsers will keep the connection open, upon receiving a ping, even if they don't properly PONG!
		# in an ideal world, we wouldn't have our own 'task' 'ping' or 'pong'; rather, we'd rely on ws.ping() or msg.type == WSMsgType.PING, to which we could respond with a PONG, but it doesn't seem that many browsers do this

async def _start_or_join_live_production(rq, dbc, production_id):
	lp = await db.start_or_join_live_production(dbc, production_id)
	if not rq.app['lps'].get(lp.lpi_id): # since there's no 'await' between this check and the line below, this should be atomic / async-safe
		rq.app['lps'][lp.lpi_id] = U.Struct(
			watchers = set(),
			drivers = set(),
			display_scheme = 2,
		)
	return lp

async def _get_arrangement_content(hd, arrangement_id, click_script, content_titler, highlight_arrangement_composition_id = None):
	content = await db.get_arrangement_content(hd.dbc, arrangement_id)
	content_div = html.detail_nested_content(content, click_script, content_titler, highlight_arrangement_composition_id)
	return content, content_div

async def _send_arrangement_content(hd, arrangement_id, click_script, content_titler, highlight_arrangement_composition_id = None):
	content, content_div = await _get_arrangement_content(hd, arrangement_id, click_script, content_titler, highlight_arrangement_composition_id)
	await hd.ws.send_json({'task': 'set_arrangement_content', 'content': content_div})
	return content

async def _ws_drive(hd):
	#TODO consider: from js: ws_send({task: "drive", action: "live", id: content_id});
	#TODO: the following -- only for payload['id'] (not None)
	#TODO: match = valid.rec_drive_div.match(hd.payload['composition_id'])
	#TODO: if not match:
	#TODO: 	raise ValueError() # treat like a failed cast

	arrangement_id = None
	phrase = None
	match hd.payload['action']:
		case 'clear':
			await asyncio.gather(*[ws.send_json({'task': 'clear'}) for ws in hd.lpi.watchers])
		case 'live_phrase_id':
			phrase_id = int(hd.payload['phrase_id'])
			phrase = await db.get_phrase(hd.dbc, phrase_id)
			div_id = hd.payload['div_id']
			await _send_phrase_to_watchers(hd, phrase)
			await _send_new_live_phrase_id_to_other_drivers(hd, div_id)
		case 'live_composition_id_DEPRECATE': # happens, e.g., when somebody clicks on "verse 3" ("header text", rather than clicking on the verse 3 "body")
			# TODO: DEPRECATE; we don't use this any more!!
			phrase = await db.get_composition_first_phrase(hd.dbc, int(hd.payload['composition_id']))
			await _send_phrase_to_watchers(hd, phrase)
			await _send_new_live_phrase_id_to_other_drivers(hd, aaa)
		case 'live_arrangement_id': # happens when somebody clicks on a new arrangement (title)
			arrangement_id = int(hd.payload['arrangement_id'])
			content = await _send_arrangement_content(hd, arrangement_id, 'drive_live_phrase', html._content_title)
			await _send_new_live_arrangement_to_other_drivers(hd, arrangement_id, content)
			if not await _handle_announcements_arrangement(hd, arrangement_id):
				# if the above returns false, then this is a "normal" arrangement, handle "normally":  TODO - this is kludgy; fix!
				await _send_new_bg_to_watchers(hd, content.background)
				await _send_phrase_to_watchers(hd, content.children[0].phrases[0]) # TODO: this is kludgy-hardcodish; fix!
		case _:
			l.error(f'''Action "{hd.payload['action']}" not recognized!''')

async def _send_phrase_to_watchers(hd, phrase):
	if phrase.content[0]['content'].endswith('.jpg'): # TODO: KLUDGY
		image = settings.k_static_url + f"images/{phrase.content[0]['content']}"
		await asyncio.gather(*[ws.send_json({'task': 'clear'}) for ws in hd.lpi.watchers])
		await asyncio.gather(*[ws.send_json({'task': 'bg', 'bg': image}) for ws in hd.lpi.watchers])
	else:
		phrase_div = html.div_phrase(phrase)
		# TODO: check now, after that DB lookup, to see if there are more drive messages on the pipe?  Then abandon the dispersal until new drive message(s) are folded in?
			
		await asyncio.gather(*[ws.send_json({
			'task': 'set_live_content', 
			'display_scheme': phrase.phrase['display_scheme'],
			'content': phrase_div,
			#TODO: 'bg': bg,
		}) for ws in hd.lpi.watchers])
		# TODO: separate "royal watchers" from plebians

async def _send_new_live_phrase_id_to_other_drivers(hd, div_id):
	await asyncio.gather(*[ws.send_json({
		'task': 'update_live_phrase_id',
		'div_id': div_id,
	}) for ws in hd.lpi.drivers if ws != hd.ws])

async def _send_new_live_arrangement_to_other_drivers(hd, arrangement_id, content):
	_, content_div = await _get_arrangement_content(hd, arrangement_id, 'drive_live_phrase', html._content_title)
	await asyncio.gather(*[ws.send_json({
		'task': 'update_live_arrangement_id',
		'arrangement_id': arrangement_id,
		'arrangement_content': content_div,
	}) for ws in hd.lpi.drivers if ws != hd.ws])

async def _send_new_bg_to_watchers(hd, background):
	await asyncio.gather(*[ws.send_json({'task': 'clear'}) for ws in hd.lpi.watchers])
	bg = settings.k_static_url + f'bgs/{background}'
	await asyncio.gather(*[ws.send_json({'task': 'bg', 'bg': bg}) for ws in hd.lpi.watchers])

async def _handle_announcements_arrangement(hd, arrangement_id):
	# Announcements TODO: kludgy!
	if arrangement_id == 20: #TODO: remove HARDCODE!
		await asyncio.gather(*[ws.send_json({'task': 'start_announcements'}) for ws in hd.lpi.watchers])
		return True #TODO: kludgy!
	else:
		await asyncio.gather(*[ws.send_json({'task': 'stop_announcements'}) for ws in hd.lpi.watchers])
		return False #TODO: kludgy!

async def _ws_edit(hd):
	#TODO: SEE TODO items in _ws_drive!

	if hd.payload['action'] == 'phrase_id':
		phrase = await db.get_phrase(hd.dbc, int(hd.payload['phrase_id']))
	#elif hd.payload['action'] == 'composition_id': # happens, e.g., when somebody clicks on "verse 3" ("header text", rather than clicking on the verse 3 "body")
	#	phrase = await db.get_composition_first_phrase(hd.dbc, int(hd.payload['composition_id']))
	elif hd.payload['action'] == 'arrangement_id': # happens when somebody clicks on a new arrangement (title)
		arrangement_id = int(hd.payload['arrangement_id'])
		content = await _send_arrangement_content(hd, arrangement_id, 'edit_phrase', html._content_title_with_edits)
		# BG:
		bg = settings.k_static_url + f'bgs/{content.background}'
		await hd.ws.send_json({'task': 'set_arrangement_bg', 'bg': bg})
		# Announcements TODO: kludgy!
		if arrangement_id == 20: #TODO: remove HARDCODE!
			pass#TODO
	elif hd.payload['action'] == 'move_composition_down':
		await _move_composition_up_down(hd, 1)
	elif hd.payload['action'] == 'move_composition_up':
		await _move_composition_up_down(hd, -1)
	elif hd.payload['action'] == 'move_arrangement_down':
		await _move_arrangement_up_down(hd, 1)
	elif hd.payload['action'] == 'move_arrangement_up':
		await _move_arrangement_up_down(hd, -1)

async def _move_composition_up_down(hd, up_down):
		ac_id = int(hd.payload['arrangement_composition_id'])
		arrangement_id = await db.move_composition_up_down(hd.dbc, ac_id, up_down)
		await _send_arrangement_content(hd, arrangement_id, 'edit_phrase', html._content_title_with_edits, ac_id)

async def _move_arrangement_up_down(hd, up_down):
		pa_id = int(hd.payload['production_arrangement_id'])
		production_id = await db.move_arrangement_up_down(hd.dbc, pa_id, up_down)
		await _send_production_content(hd, production_id, 'edit_phrase', html._content_title_with_edits, pa_id)

async def _send_production_content(hd, production_id, click_script, content_titler, production_arrangement_id_to_highlight = None):
	arrangement_titles = await db.get_production_arrangement_titles(hd.dbc, production_id)
	if not arrangement_titles:
		first_arrangement_content = []
	else:
		if production_arrangement_id_to_highlight: 
			first_arrangement_content = await db.get_production_arrangement_content(hd.dbc, production_arrangement_id_to_highlight)
		else:
			first = arrangement_titles[0] # just use the first arrangement in the production...
			first_arrangement_content = await db.get_arrangement_content(hd.dbc, first.arrangement_id)
			production_arrangement_id_to_highlight = first.production_arrangement_id

	production_content_div = html.build_left_arrangement_titles(arrangement_titles, 'load_arrangement', True, production_arrangement_id_to_highlight)
	arrangement_content_div = html.detail_nested_content(first_arrangement_content, click_script, content_titler)
	await hd.ws.send_json({'task': 'set_production_and_arrangement_content', 'production_content': production_content_div, 'arrangement_content': arrangement_content_div})

async def _ws_fetch_new_announcement(hd):
	global g_announcement_id
	global g_announcements
	url = settings.k_static_url + f'announcements/{g_announcements[g_announcement_id]}'
	g_announcement_id = (g_announcement_id + 1) % len(g_announcements)
	await asyncio.gather(*[ws.send_json({'task': 'next_announcement', 'url': url}) for ws in hd.lpi.watchers])
	

'''
async def _ws_watch(hd):
	watcher = asyncio.create_task(_relay_drive_actions(hd.ws))
	asyncio.wait_for(watcher, None)

async def _relay_drive_actions(ws):
	# One of these is spun (via asyncio.create_task()) for each "watcher" client
	while True:
		#await g_drive_event.wait()
		await ws.send_json({'task': 'set_live_content', 'content': g_live_content})
'''

# Etc.

async def _set_up_common_view(view, dbc = True, uuid = True, data = True, re_log_in_seconds = None):
	result = U.Struct(rq = view.request, session = await get_session(view.request))
	if dbc:
		result.dbc = result.rq.app['db'] # TODO: .cursor()
	if uuid:
		result.uuid = result.session.get('uuid')
	if data:
		result.data = await result.rq.post()
	if not re_log_in_seconds:
		return result # done!
	# else...
	login_time = result.session.get('login_time')
	if not result.session.get('uuid') or not login_time: # use result.session.get('uuid') b/c there's no guarantee that uuid=True in args
		_add_flash_m(result.session, text.login_required)
	elif time.time() - login_time > re_log_in_seconds: # we know login_time is non-None, by now; confirm that user logged in within the last re_log_in_seconds seconds, else redirect to login
		_add_flash_m(result.session, text.verify_login_required)
	else:
		return result # all is good; we only want the next two lines if either of the above tests failed and we have flash_m (and have to re-present login page):
	result.session['after_login'] = str(result.rq.url) # come back here after logging in
	raise web.HTTPFound(_gurl(result.rq, 'login'))

async def _set_up_common_view_get(view, dbc = False, re_log_in_seconds = None):
	return await _set_up_common_view(view, dbc, uuid = False, data = False, re_log_in_seconds = re_log_in_seconds)

async def _set_up_common_view_post(view, dbc = True, uuid = True, data = True, re_log_in_seconds = None):
	return await _set_up_common_view(view, dbc, uuid = uuid, data = data, re_log_in_seconds = re_log_in_seconds)


# Init / Shutdown -------------------------------------------------------------

async def init_db(filename):
	conn = await aiosqlite.connect(filename, isolation_level = None, detect_types = PARSE_DECLTYPES) # "isolation_level = None disables the Python wrapper's automatic handling of issuing BEGIN etc. for you. What's left is the underlying C library, which does do "autocommit" by default. That autocommit, however, is disabled when you do a BEGIN (b/c you're signaling a transaction with that statement" - from https://stackoverflow.com/questions/15856976/transactions-with-python-sqlite3 - thanks Thanatos
	conn.row_factory = aiosqlite.Row
	await conn.execute('pragma journal_mode = wal') # see https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/ - since we're using async/await from a wsgi stack, this is appropriate
	await conn.execute('pragma foreign_keys = ON')
	#await conn.execute('pragma case_sensitive_like = true')
	#await conn.set_trace_callback(l.debug) - not needed with aiosqlite, anyway
	return conn # consider conn.cursor(), instead, according to more "typical" use; sqlite3 has an "efficient" approach that involves just using the database directly (a temp cursor is auto-created under the hood): https://pysqlite.readthedocs.io/en/latest/sqlite3.html#using-sqlite3-efficiently

async def _init(app):
	l.info('Initializing database...')
	app['db'] = await init_db('threeslides-2022.db')
	#app['db'] = await init_db('working.db')
	app['lps'] = {}
	l.info('...database initialized')
	
async def _shutdown(app):
	l.info('Shutting down...')
	if 'db' in app:
		await app['db'].close()
	for lpi, lp in app['lps'].items():
		for ws in lp.watchers:
			await ws.close()
	l.info('...shutdown complete')


# Run server like so, from cli:
#		python -m aiohttp.web -H localhost -P 8080 main:init
# Or, using adev (from parent directory!) (TYPICAL):
#		adev runserver -s static --livereload app
# Or... (older?)
#		adev runserver --app-factory init --livereload --debug-toolbar test1_app
async def init(argv):
	app = web.Application()

	# Set up sessions:
	fernet_key = fernet.Fernet.generate_key()
	secret_key = base64.urlsafe_b64decode(fernet_key)
	setup_session(app, EncryptedCookieStorage(secret_key))
	# Tried both of the following; running a redis server or memcached server, they basically work; not sure I want the dependencies right now
	#redis = await aioredis.create_redis_pool('redis://localhost')
	#setup_session(app, RedisStorage(redis))
	#mc = aiomcache.Client('localhost', 11211)
	#setup_session(app, memcached_storage.MemcachedStorage(mc))

	# Add standard routes:
	app.add_routes(rt)
	
	# Add startup/shutdown hooks:
	app.on_startup.append(_init)
	app.on_shutdown.append(_shutdown)

	return app


def app():
	return init(None)

