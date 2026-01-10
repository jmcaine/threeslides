__author__ = 'J. Michael Caine'
__copyright__ = '2022'
__version__ = '0.1'
__license__ = 'MIT'

import aiosqlite
import asyncio
import functools
import io
import json
import logging
import pathlib
import re
import socket
import time
import traceback

from dataclasses import dataclass

import datetime as dt

from os.path import exists as path_exists
from os import listdir

from uuid import uuid4
from cryptography import fernet
import base64


from sqlite3 import PARSE_DECLTYPES

from PIL import Image
import cv2


from aiohttp import web, WSMsgType, WSCloseCode
from aiohttp_session import setup as setup_session, get_session, new_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
# Tried both of the following; running a redis server or memcached server, they basically work; not sure I want the dependencies right now
#from aiohttp_session.redis_storage import RedisStorage
#import aioredis
#from aiohttp_session import memcached_storage
#fmport aiomcache
# TODO: Note warning in debug/console client-side: '''Cookie “AIOHTTP_SESSION” does not have a proper “SameSite” attribute value. Soon, cookies without the “SameSite” attribute or with an invalid value will be treated as “Lax”. This means that the cookie will no longer be sent in third-party contexts. If your application depends on this cookie being available in such contexts, please add the “SameSite=None“ attribute to it. To know more about the “SameSite“ attribute, read https://developer.mozilla.org/docs/Web/HTTP/Headers/Set-Cookie/SameSite''' -- see set_cookie, with samesite arg, in https://docs.aiohttp.org/en/stable/web_reference.html ... but we're probably talking about some core setting that will auto-apply to the “AIOHTTP_SESSION” cookie itself, which we don't set explicitly ourselves.

from yarl import URL

from . import html
from . import db
from . import valid
from . import exception
from . import text
from . import settings
from . import util as U
from .shared import *


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

utfencode = lambda st: st.encode('utf-8')
utfdecode = lambda st: st.decode('utf-8')


#TODO!!: put ALL of this "global" stuff into app['key'] storage instead of leaving global like this!  see https://docs.aiohttp.org/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
# Can't store coroutines in sessions, directly; not even redis or memcached directories, so we store them in global memory, in this dict:
g_twixt_work = {} # TODO: note, we 'del g_twixt_work[twixt_id]' and 'del session['twixt_id']' "as we go", but there's a real possibility of abandonment (as in, a page fails to fully load or to create the ws in its javascript, so the first ws_messages call never issues) -- so we should make a watchdog that cleans this out occasionally; thus, we'd need timestamps on the items within, as well


#NOTE: we used to use hd.session['current_ac_id'] and ...'current_phrase'..., but we need all drivers to be on the same page; we actually need another concept, of a "current show" or something, to which all drivers are connected, so that a server can run more than one show simultaneously if wanted (maybe we need this?  It would be more of a centralized-server model, rather than a server-at-the-prjector-itself model....)
g_current_ac_id = 0
g_current_phrase_id = 0


@dataclass
class RCIndex:
	scroll_to_index: int
	media_path: str
g_current_rich_content_indeces = []
g_current_rich_content_current_index = 0
k_thumb_appendix = '.small.jpg'

# Utils -----------------------------------------------------------------------

rt = web.RouteTableDef()
def hr(text): return web.Response(text = text, content_type = 'text/html')

# TEMP, DEBUG!!!!  (for running with:
#   python -m aiohttp.web -H 0.0.0.0 -P 8080 app.main:init
# "raw", and to get /static
if settings.debug:
	rt.static('/static', settings.debug_static)


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


@rt.get('/testquill')
async def testquill(rq):
	# This is the current favorite
	return hr(html.testquill(_origin(rq), _ws_url(rq)))
@rt.get('/testpell')
async def testpell(rq):
	# Not as good as Quill
	return hr(html.testpell(_origin(rq), _ws_url(rq)))


@rt.get('/select_song')
async def select_song(rq):
	#TODO: session = await get_session(rq)
	dbc = rq.app['db']
	songs = await db.get_compositions_by_tag_name(dbc, 'Song')
	return hr(html.select_song(_origin(rq), songs))

@rt.get('/select_song_arrangement')
async def select_song_arrangement(rq):
	#TODO: session = await get_session(rq)
	dbc = rq.app['db']
	arrangements = await db.get_arrangements_by_tag_name(dbc, 'Song')
	return hr(html.select_song_arrangement(_origin(rq), arrangements))


@rt.get('/detail/song/{composition_id}')
async def detail_song(rq):
	#TODO: session = await get_session(rq)
	composition_id = rq.match_info['composition_id']
	dbc = rq.app['db']
	song = await db.get_composition_content(dbc, composition_id)
	return hr(html.detail_song(_origin(rq), song))

@rt.get('/detail/song_arrangement/{arrangement_id}')
async def detail_song_arrangement(rq):
	#TODO: session = await get_session(rq)
	arrangement_id = rq.match_info['arrangement_id']
	dbc = rq.app['db']
	song = await db.get_arrangement_content(dbc, arrangement_id)
	return hr(html.detail_song(_origin(rq), song))


@rt.get('/drive/{production_id}')
async def drive(rq):
	#TODO: session = await get_session(rq)
	
	lp = await _start_or_join_live_production(rq, rq.app['db'], int(rq.match_info['production_id']))
	return hr(html.drive(_origin(rq), _ws_url(rq), lp))


@rt.get('/watch/{production_id}')
async def watch(rq):
	show_hidden = bool(rq.query.get('show_hidden', False))
	cut_frame = bool(rq.query.get('cut_frame', False))
	monitor = bool(rq.query.get('monitor', False))
	primary = bool(rq.query.get('primary', False))
	session = await get_session(rq)
	session['config'] = {
		'show_hidden': show_hidden,
		'cut_frame': cut_frame,
		'monitor': monitor,
		'primary': primary,
		'font_size': 'large',
		'font_format': 'halo',
		'flatten_phrases': False,
	}
	lp = await _start_or_join_live_production(rq, rq.app['db'], int(rq.match_info['production_id']))
	return hr(html.watch(_origin(rq), _ws_url(rq), lp, show_hidden, cut_frame))

@rt.get('/watch_captioned/{production_id}')
async def watch_captioned(rq):
	#session = await get_session(rq)
	session = await get_session(rq)
	session['config'] = {
		'show_hidden': False,
		'cut_frame': False,
		'monitor': False,
		'primary': False,
		'font_size': 'small',
		'font_format': 'halo', #'outlined',
		'flatten_phrases': True
	}
	lp = await _start_or_join_live_production(rq, rq.app['db'], int(rq.match_info['production_id']))
	return hr(html.watch_captioned(_origin(rq), _ws_url(rq), lp))

# ------------------------

class Edit_Production_Service(web.View):

	async def get(self):
		z = await _set_up_common_get(self.request, dbc = True)
		pid = int(z.rq.match_info['production_id'])
		if pid:
			production = await db.get_production(z.dbc, pid)
			upcomings = None
			templates = None
		else:
			production = None
			upcomings = await db.get_coming_productions(z.dbc)
			templates = await db.get_production_templates(z.dbc) # TODO: add site-id, to filter particular site's own templates!

		return hr(html.edit_production(html.Form(z.rq.rel_url), self._title(), _origin(self.request), production, upcomings, templates))

	async def post(self):
		z = await _set_up_common_post(self.request)
		invalids = [] #TODO...  _validate_regex(z.data, invalids, ( ...
		try:
			d = dt.date.fromisoformat(z.data['date'])
			t = dt.time.fromisoformat(z.data['time'])
			dttm = dt.datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)
			pid = int(z.rq.match_info['production_id'])
			if pid:
				#TODO: check login credentials before going on! (ensure that user has access to this production
				await db.edit_production(z.dbc, pid, z.data['name'], dttm.isoformat())
			else: # no pid means: new production
				# Create brand new production:
				pid = await db.create_production(z.dbc, z.data['name'], dttm.isoformat(), z.data.get('template'))
			raise web.HTTPFound(_gurl(z.rq, f'edit_production_arrangements', {'production_id': str(pid)}))
		except web.HTTPRedirection:
			raise # move on
		except: # TODO: differentiate, and add errors to hr!
			l.error(traceback.format_exc())
			if pid:
				production = await db.get_production(z.dbc, pid)
				templates = None
			else:
				production = None
				templates = await db.get_production_templates(z.dbc) # TODO: add site-id, to filter particular site's own templates!
			return hr(html.edit_production(html.Form(z.rq.rel_url, z.data, invalids), self._title(), _origin(self.request), production, None, templates))

@rt.get('/create_production', name = 'create_production')
async def create_production(rq):
	raise web.HTTPFound(_gurl(rq, f'edit_production', {'production_id': '0'})) # 0 is signal that this is a brand new production
@rt.get('/create_service', name = 'create_service')
async def create_service(rq):
	raise web.HTTPFound(_gurl(rq, f'edit_service', {'production_id': '0'})) # 0 is signal that this is a brand new production

class Production:
	def _title(self):
		return 'Production'
class Service:
	def _title(self):
		return 'Service'

@rt.view('/edit_production/{production_id}', name = 'edit_production')
class Edit_Production(Edit_Production_Service, Production):
	pass
@rt.view('/edit_service/{production_id}', name = 'edit_service')
class Edit_Service(Edit_Production_Service, Service):
	pass


# ------------------------

@rt.get('/edit_production_arrangements/{production_id}', name = 'edit_production_arrangements')
async def edit_production_arrangements(rq):
	z = await _set_up_common_get(rq, dbc = True)
	#TODO: check login credentials before going on! (ensure that user has access to this production
	pid = z.rq.match_info['production_id']
	production = await db.get_production(z.dbc, pid)
	arrangement_titles = await db.get_production_arrangement_titles(z.dbc, pid)
	first_arrangement_content = await db.get_arrangement_content(z.dbc, arrangement_titles[0].arrangement_id) if arrangement_titles else None
	available_compositions = await db.get_available_compositions(z.dbc, arrangement_titles[0].arrangement_id) if arrangement_titles else None
	return hr(html.edit_production_arrangements(_ws_url(z.rq), html.Form(z.rq.rel_url), _origin(rq), production, arrangement_titles, first_arrangement_content, available_compositions))



@rt.view('/create_arrangement', name = 'create_arrangement')
class Create_Arrangement(web.View):
	async def get(self):
		z = await _set_up_common_get(self.request, dbc = True)
		return hr(html.new_arrangement(html.Form(z.rq.rel_url)))

	async def post(self):
		try:
			z = await _set_up_common_post(self.request)
			invalids = [] #TODO...  _validate_regex(z.data, invalids, ( ...
			arrangement_id = await db.create_arrangement(z.dbc, z.data['name']) # TODO - more args! head-composition (?? and composition arrangement (v1, v2, etc.)!!!)
			raise web.HTTPFound(_gurl(z.rq, 'edit_arrangement', {'arrangement_id': str(arrangement_id)}))

		except web.HTTPRedirection:
			raise # move on
		except: # TODO: differentiate, and add errors to hr!
			l.error('EXCEPTION in Create_Arrangement::post(): ' + traceback.format_exc())
			return hr(html.new_arrangement(html.Form(z.rq.rel_url)))


# ----------------------------------------------------------------

async def _ws_aux_handler(rq, if_collection_name):
	ws = None
	try:
		ws = web.WebSocketResponse() # web.WebSocketResponse(max_msg_size = 1024 * 1024 * 500) # does this do anything?  Think the main max-out problem is treated in nginx or supervisor setup
		await ws.prepare(rq)
		l.info(f'Adding an interface to {if_collection_name}...')
		rq.app[if_collection_name].append(ws)
		try:
			async for msg in ws:
				if msg.type == WSMsgType.TEXT:
					pass # we don't actually expect any messages yet; we just send them
					#payload = json.loads(msg.data)
				elif msg.type == WSMsgType.ERROR:
					raise ws.exception()
		except Exception as e:
			l.error(traceback.format_exc())
			l.error(f'Exception processing messages for {if_collection_name}; shutting down this interface...')
		finally:
			rq.app[if_collection_name].remove(ws)
	except:
		l.error(traceback.format_exc())
	return ws

@rt.get('/ws_obs')
async def ws_obs(rq):
	return await _ws_aux_handler(rq, 'obs_ifs')

@rt.get('/ws_xair')
async def ws_xair(rq):
	return await _ws_aux_handler(rq, 'xair_ifs')

@rt.get('/ws_bg_music')
async def ws_bg_music(rq):
	return await _ws_aux_handler(rq, 'bg_music_ifs')

@rt.get('/ws_qlc')
async def ws_qlc(rq):
	return await _ws_aux_handler(rq, 'qlc_ifs')

@rt.get('/ws')
async def ws(rq):
	ws = web.WebSocketResponse()
	await ws.prepare(rq)
	session = await get_session(rq)

	handlers = {
		#'init': _ws_init, --- 'init' is handled specially, after all, before normal processing...
		'init': _ignore_message,
		'ping': _ws_ping_pong,
		'drive': _ws_drive,
		'edit': _ws_edit,
		'add_watcher': _ws_add_watcher,
		'add_driver': _ws_add_driver,
		'next_auto_advance': _ws_next_auto_advance,
		'reload_all_watchers': _ws_reload_all_watchers,
	}
	
	hd = handler_data = U.Struct( # TODO: use @dataclass instead! (this code predated dataclasses in python!)
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
		# Handshake carefully (necessary... see code/comments below for some detail, as well as ws.onopen() in drive.js or edit.js):
		l.info('new websocket established; hand-shaking...')
		await ws.send_json({'task': 'init'})
		while True:
			try:
				hd.payload = await ws.receive_json(timeout = 0.2)
				assert hd.payload['task'] == 'init', "initial message must be an 'init' response"
				await _ws_init(hd)
				break # out of while loop
			except asyncio.TimeoutError as e: # timed out; try again:
				await ws.send_json({'task': 'init'}) # it seems that initial sends will often fail, as, though the web socket was set up by the client side, initially, and we're handling the opening of this socket here in this function, and have called ws.prepare() and everything... still, sometimes the initial 'init' sent goes unheaded; likewise, if we initialize the send from the client, it often isn't read here.  One solution seems to be to always wait a second before sending the initial, but this tight while-loop is more robust
		l.info('... "init" handshake complete; websocket ready for normal messages.')

		# Now we can begin indefinitely processing normal messages:
		async for msg in ws:
			if msg.type == WSMsgType.ERROR:
				raise ws.exception()
			elif msg.type == WSMsgType.TEXT:
				hd.payload = json.loads(msg.data) # Note: payload validated in real msg_handlers, later
				await handlers[hd.payload['task']](hd)
			elif msg.type == WSMsgType.BINARY:
				await _ws_binary(hd, msg.data)

	except Exception as e:
		l.error(traceback.format_exc())
		l.error('Exception processing WS messages; shutting down WS...')

	if hasattr(hd, 'lpi'):
		#TODO!NEED to match on predicate (can't figure out how), on lpi.watchers... lpi.watchers is now a UStruct -- hd.lpi.watchers.discard(ws)
		#TODO: instead of any of this, we could just always react upon ws_send-broadcasting messages; if the send fails (b/c the ws is closed), then delete it from our set then...?
		if ws in hd.lpi.watchers:
			del hd.lpi.watchers[ws]
		hd.lpi.drivers.discard(ws)
	l.info('websocket connection closed (ws_drive)')
	return ws



# Utils ----------------------------------------

_gurl = lambda rq, name, parts = {}: str(rq.app.router[name].url_for(**parts))

def _origin(rq):
	result = rq.url
	if settings.debug:
		result = URL.build(scheme = result.scheme, host = result.host, port = settings.k_port) # a bit of a kludge - comes from using adev, normally, for debugging, which serves static on a different port
	return str(result.origin())


def _ws_url(rq, name = None):
	# Builds a url from `rq` (host part, mainly) and `name`, as a websocket-schemed version; e.g.
	#	http://domain.tld/quiz/history/sequence --> ws://domain.tld/<name>
	return URL.build(scheme = 'ws', host = rq.host, path = name if name else '/ws')

async def _ignore_message(hd):
	l.info('got a message that we should ignore; e.g., an extra "init", due to startup irregularity')

async def _ws_init(hd):
	if 'lpi_id' in hd.payload:
		hd.lpi_id = hd.payload['lpi_id'] # lpi = "live production INDEX"; lpi_id = id of that index record in DB
		hd.lpi = hd.rq.app['lps'][hd.lpi_id]

async def _ws_add_watcher(hd):
	hd.lpi.watchers[hd.ws] = U.Struct(config = hd.session['config'])


async def _ws_add_driver(hd):
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
			watchers = {},
			drivers = set(),
			display_scheme = 2,
		)
	return lp

async def _get_arrangement_content(hd, arrangement_id, click_script, content_titler, include_available_compositions = False, highlight_arrangement_composition_id = None):
	content = await db.get_arrangement_content(hd.dbc, arrangement_id)
	available_compositions = None # unless...
	if include_available_compositions:
		available_compositions = await db.get_available_compositions(hd.dbc, arrangement_id)
	content_div = html.detail_nested_content(_origin(hd.rq), content, click_script, content_titler, available_compositions, highlight_arrangement_composition_id)
	return content, content_div

async def _send_arrangement_content(hd, arrangement_id, click_script, content_titler, include_available_compositions = False, highlight_arrangement_composition_id = None):
	content, content_div = await _get_arrangement_content(hd, arrangement_id, click_script, content_titler, include_available_compositions, highlight_arrangement_composition_id)
	await hd.ws.send_json({'task': 'set_arrangement_content', 'content': content_div})
	return content

async def _set_new_live_phrase(hd, ac_id, phrase_id, exclude_self = True):
	global g_current_ac_id # see the NOTE on g_current_ac_id declaration!
	global g_current_phrase_id # see the NOTE on g_current_phrase_id declaration!
	g_current_ac_id = ac_id # for next time 'round
	g_current_phrase_id = phrase_id # for next time 'round
	#NOTE: the following is how we used to do it, see NOTEs on g_current_ac_id and g_current_phrase_id declarations
	#hd.session['current_ac_id'] = ac_id # see the NOTE on g_current_ac_id declaration!
	#hd.session['current_phrase_id'] = phrase_id # see the NOTE on g_current_phrase_id declaration!
	phrase = await db.get_phrase(hd.dbc, phrase_id)

	global g_current_rich_content_indeces
	global g_current_rich_content_current_index
	g_current_rich_content_indeces = []
	g_current_rich_content_current_index = 0
	if phrase.content_type == 2: # TODO: hardcode content_type!!!
		assert len(phrase.content) == 1, 'type-2 content (rich text) only comes in a one-content-record-per-phrase flavor'
		# These next few lines rely heavily on the design of the quill rich-text data scheme, called "Delta", which is a dict that looks something like: {"ops": [ {"insert":"Hello "}, ...}
		content = phrase.content[0]['content']
		scroll_to_index = 0
		media_path = None
		for d in json.loads(content)['ops']:
			if 'insert' in d:
				ins = d['insert']
				if isinstance(ins, str):
					scroll_to_index += len(ins)
				elif isinstance(ins, dict) and 'image' in ins:
					media_path = ins['image']
					scroll_to_index += 1 # every image counts as one more for "scroll-to", in Quill
					g_current_rich_content_indeces.append(RCIndex(scroll_to_index, media_path))

		# Update all drivers (yes, including the primary driver causing this action in the first place):
		await asyncio.gather(*[ws.send_json({
			'task': 'show_rich_composition_content',
			'content': content,
		}) for ws in hd.lpi.drivers])
		# ...and update all watchers with the first image in the set:
		await _send_media_to_watchers(hd, g_current_rich_content_indeces[0].media_path.rstrip(k_thumb_appendix))

	elif phrase.content_type == 3: # TODO: hardcode content_type!!! (3 == auto-advance, e.g., "announcements" movies)
		if not await _send_media_phrase_to_watchers(hd, ac_id, phrase, 1):
			l.error('auto-advance content requested, but no content at all, or no media file (the only payload should be an mp4 (etc.) path).')

	else: #?TODO OR, make `phrase` something that can indeed be sent, in-tact, to watchers (and other drivers?!?) - think this just needs to biffurcate here
		await _send_phrase_to_watchers(hd, ac_id, phrase)
		await _send_new_live_phrase_id_to_drivers(hd, html.phrase_div_id(ac_id, phrase_id), exclude_self)


async def drive_forward(hd):
	global g_current_rich_content_current_index
	global g_current_rich_content_indeces
	if len(g_current_rich_content_indeces) > 0:
		g_current_rich_content_current_index = min(g_current_rich_content_current_index + 1, len(g_current_rich_content_indeces) - 1)
		#"wrapping" version: g_current_rich_content_current_index = (g_current_rich_content_current_index + 1) % len(g_current_rich_content_indeces)
		await _drive_x_update_all(hd, g_current_rich_content_indeces[g_current_rich_content_current_index], False)
	else:
		await _drive_x_phrase(hd, db.get_next_phrase)

async def drive_back(hd):
	global g_current_rich_content_current_index
	global g_current_rich_content_indeces
	if len(g_current_rich_content_indeces) > 0:
		g_current_rich_content_current_index = max(g_current_rich_content_current_index - 1, 0)
		await _drive_x_update_all(hd, g_current_rich_content_indeces[g_current_rich_content_current_index], False)
	else:
		await _drive_x_phrase(hd, db.get_previous_phrase)

async def drive_selection(hd):
	global g_current_rich_content_current_index
	global g_current_rich_content_indeces
	previous = 0
	cursor = int(hd.payload['cursor'])
	rci = None
	for i in range(len(g_current_rich_content_indeces) - 1):
		rci = g_current_rich_content_indeces[i + 1]
		if previous <= cursor and cursor < rci.scroll_to_index:
			g_current_rich_content_current_index = i
			rci = g_current_rich_content_indeces[i]
			break
		previous = rci.scroll_to_index
	await _drive_x_update_all(hd, rci, True)

async def _drive_x_update_all(hd, rich_content_index, exclude_self = True):
	exclusion = ws != hd.ws if exclude_self else True
	# Send update to watchers:
	filepath = re.sub(fr'{k_thumb_appendix}\?cache_bust=[0-9][0-9][0-9][0-9]', '', rich_content_index.media_path)
	await _send_media_to_watchers(hd, filepath)
	# Update drivers' positions:
	await asyncio.gather(*[ws.send_json({
		'task': 'update_live_rich_content_position',
		'selection_idx': rich_content_index.scroll_to_index,
	}) for ws in hd.lpi.drivers if exclusion])
	# And move to designated camera/obs scene:
	await asyncio.gather(*[ws.send_str('slide_scene') for ws in hd.rq.app['obs_ifs']])


async def _drive_x_phrase(hd, func):
	global g_current_ac_id
	global g_current_phrase_id
	phrase_id = await func(hd.dbc, g_current_ac_id, g_current_phrase_id)
	if phrase_id:
		await _set_new_live_phrase(hd, g_current_ac_id, phrase_id, False)
	# else, do NOTHING! (probably at the end of the line - last phrase in the composition)


async def play_bg_music(hd):
	await asyncio.gather(*[ws.send_str('startstop') for ws in hd.rq.app['bg_music_ifs']])

async def play_bg_skip(hd):
	await asyncio.gather(*[ws.send_str('skip') for ws in hd.rq.app['bg_music_ifs']])

async def restore_lights(hd):
	await asyncio.gather(*[ws.send_str('restore') for ws in hd.rq.app['qlc_ifs']])

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
			await asyncio.gather(*[ws.send_json({'task': 'clear'}) for ws in hd.lpi.watchers.keys()])
		case 'live_phrase_id':
			await _set_new_live_phrase(hd, int(hd.payload['ac_id']), int(hd.payload['phrase_id']))
		case 'live_arrangement_id': # happens when somebody (in /drive) clicks on a new arrangement (title)
			arrangement_id = int(hd.payload['arrangement_id'])
			content = await _send_arrangement_content(hd, arrangement_id, 'drive_live_phrase', html._content_title)
			await _send_new_live_arrangement_to_other_drivers(hd, arrangement_id, content)
			await _send_new_bg_to_watchers(hd, content.background)
			#REMOVED the following two lines - don't really want to auto-load first phrase, after all; always let user do it manually; always start with "blank screen" (or, "background screen", more likely)
			#if content.children and content.children[0].phrases:
			#	await _send_phrase_to_watchers(hd, acid, content.children[0].phrases[0])
		case 'select_blank':
			await asyncio.gather(*[ws.send_json({'task': 'set_live_content_blank'}) for ws in hd.lpi.watchers.keys()])
		case 'play_bg_music':
			await play_bg_music(hd)
		case 'play_bg_skip':
			await play_bg_skip(hd)
		case 'play_video':
			await asyncio.gather(*[ws.send_json({'task': 'play_video'}) for ws in hd.lpi.watchers.keys()])
		case 'pause_video':
			await asyncio.gather(*[ws.send_json({'task': 'pause_video'}) for ws in hd.lpi.watchers.keys()])
		case 'reset_video':
			await asyncio.gather(*[ws.send_json({'task': 'reset_video'}) for ws in hd.lpi.watchers.keys()])
		case 'forward':
			await drive_forward(hd)
		case 'back':
			await drive_back(hd)
		case 'selection':
			await drive_selection(hd)
		case 'restore_lights':
			await restore_lights(hd)
		case _:
			l.error(f'''Action "{hd.payload['action']}" not recognized!''')

async def _send_media_phrase_to_watchers(hd, ac_id, phrase, auto_advance_notify):
	txt = str(phrase.content[0]['content']) if phrase.content and len(phrase.content) >= 1 else ''
	if txt and txt.lower().endswith(k_video_formats + k_audio_formats + k_image_formats):
		duration = 0 # default - no auto-advance duration
		if txt[2] == '*': # expected format 'dd*<filepath>' if txt[2] == * ... 'dd' is a two-digit "seconds" indicator
			try: duration = int(txt[0:2]) # currently, this rather "overrides" auto_advance_notify - even if that's 0 or False, this results in an auto-advance situation
			except: pass
			txt = txt[3:] # remove prefix
		await _send_media_to_watchers(hd, f'/static/uploads/{ac_id}/{txt}', auto_advance_notify = auto_advance_notify, duration = duration)
		return True
	return False

async def _send_phrase_to_watchers(hd, ac_id, phrase):
	if not await _send_media_phrase_to_watchers(hd, ac_id, phrase, 0):
		# it's a regular phrase, not a media phrase, so...
		sends = []
		for ws, watcher in hd.lpi.watchers.items(): # TODO: separate "royal watchers" from plebians?
			sends.append(ws.send_json({
				'task': 'set_live_content',
				'display_scheme': phrase.phrase['display_scheme'],
				'content': html.div_phrase(watcher.config, phrase), # TODO: would be more efficient to call this just once (or once per config?!), but that's just it: the number of possibilities for different views on this, based on configs, could be ridiculous; might-as-well just construct each for each watcher
				#TODO: 'bg': bg,
			}))
			# TODO: check now, after each, to see if there are more drive messages on the pipe that might just render these null and void?  Then abandon the dispersal until new drive message(s) are folded in?
		await asyncio.gather(*sends)
		

async def _send_new_live_phrase_id_to_drivers(hd, div_id, exclude_self = True):
	exclusion = ws != hd.ws if exclude_self else True
	await asyncio.gather(*[ws.send_json({
		'task': 'update_live_phrase_id',
		'div_id': div_id,
	}) for ws in hd.lpi.drivers if exclusion])

async def _send_new_live_arrangement_to_other_drivers(hd, arrangement_id, content):
	_, content_div = await _get_arrangement_content(hd, arrangement_id, 'drive_live_phrase', html._content_title)
	await asyncio.gather(*[ws.send_json({
		'task': 'update_live_arrangement_id',
		'arrangement_id': arrangement_id,
		'arrangement_content': content_div,
	}) for ws in hd.lpi.drivers if ws != hd.ws])

async def _send_media_to_watchers(hd, path, repeat = 0, auto_advance_notify = 0, duration = 0):
	#OLD: image = origin + f"/static/images/{path}" and ... /videos/...
	origin = _origin(hd.rq)
	path = origin + path #'/static/uploads/{meta["acid"]}/' + path
	if path.lower().endswith(k_image_formats):
		await asyncio.gather(*[ws.send_json({'task': 'clear'}) for ws in hd.lpi.watchers.keys()])
		await asyncio.gather(*[ws.send_str('mute_dp') for ws in hd.rq.app['xair_ifs']]) # a little overkill, to mute every slide, but knowing when a video has finished playing on the device that needs its channel muted at the end is also a little complicated....
		await asyncio.gather(*[ws.send_json({
			'task': 'image',
			'image': path,
			'auto_advance_notify': auto_advance_notify if watcher.config['primary'] else 0,
			'duration': duration if watcher.config['primary'] else 0,
		}) for ws, watcher in hd.lpi.watchers.items()]) # TODO: check watcher.config here, for 'show_hidden', instead of maintaining variable in watch.js?!  AND, TODO: auto_advance_notify!?
	elif path.lower().endswith(k_video_formats + k_audio_formats):
		if path.lower().endswith(k_video_formats):
			await asyncio.gather(*[ws.send_json({'task': 'clear'}) for ws in hd.lpi.watchers.keys()])
		if 'Unmute' in path or 'Ann' in path:
			await asyncio.gather(*[ws.send_str('unmute_dp') for ws in hd.rq.app['xair_ifs']])
		if 'Brownout' in path or 'Ann' in path:
			await asyncio.gather(*[ws.send_str('brownout') for ws in hd.rq.app['qlc_ifs']])
		if 'Blackout' in path:
			await asyncio.gather(*[ws.send_str('blackout') for ws in hd.rq.app['qlc_ifs']])
		await asyncio.gather(*[ws.send_json({
			'task': 'video',
			'video': path if not watcher.config['monitor'] else _monitor_version_of(path),
			'repeat': repeat,
			'auto_advance_notify': auto_advance_notify if watcher.config['primary'] else 0,
			'duration': duration if watcher.config['primary'] else 0, # TODO: currently this is ignored for movies - the entire movie length itself is just run; is this what we want?
		}) for ws, watcher in hd.lpi.watchers.items()]) # TODO: check watcher.config here, for 'show_hidden', instead of maintaining variable in watch.js?!

_monitor_version_of = lambda path: path[:path.rfind('.mp4')] + '-monitor.mp4' # TODO: handle others in k_video_formats!


async def _send_new_bg_to_watchers(hd, background):
	if background: # no-op, otherwise
		await _send_media_to_watchers(hd, '/static/uploads/bgs/' + background, repeat = 1)


async def _ws_binary(hd, data):
	assert data[0] == ord('!'), '"magic byte" ! needed to indicate this is a file upload (by convention)'
	delimiter = b'\r\n\r\n'
	idx = data.find(delimiter)
	meta = json.loads(data[1:idx]) # '1' to get past the "magic byte" ('!')
	meta['files'] = json.loads(meta['files'])
	payload = data[idx+len(delimiter):]
	assert meta['action'] == 'upload_files', '"upload_files" is the only action (currently) tied to a binary upload'
	reply_type = meta['reply_type']
	path = f'static/uploads/{meta["acid"]}/' # use the acid id # to uniquely partition off these file uploads from other (potentially similarly-named) uploads
	pathlib.Path(path).mkdir(parents = False, exist_ok = True) # parent dirs (static/uploads) should always already exist (and acid shouldn't have any slashes, ..s, etc.; should be just a number)
	pos = 0
	names = []
	thumbs = []
	for fil in meta['files']:
		name = fil['name'] # TODO: sanitize fil['name'] first!!
		names.append(name)
		size = fil['size']
		fp = path + name
		if name.lower().endswith(k_video_formats):
			with open(fp, "wb") as file:
				file.write(payload[pos:pos+size])
			vid = cv2.VideoCapture(fp)
			vid.set(cv2.CAP_PROP_POS_FRAMES, int(vid.get(cv2.CAP_PROP_FRAME_COUNT)) / 2) # get thumbnail from half-way frame (because the first umpteen are often black, in a fade-from-black)
			result, image = vid.read()
			assert result == True, "FAILED to capture frame!"
			thumb = cv2.resize(image, (k_thumbnail_size, k_thumbnail_size * 10 // 16))
			cv2.imwrite(fp + k_thumb_appendix, thumb)
		elif name.lower().endswith(k_image_formats):
			img = Image.open(io.BytesIO(payload[pos:pos+size])).convert("RGB")
			img.save(fp)
			img.thumbnail((k_thumbnail_size, k_thumbnail_size)) # modifies img in-place
			img.save(fp + k_thumb_appendix)
		elif name.lower().endswith(k_audio_formats):
			with open(fp, "wb") as file:
				file.write(payload[pos:pos+size])
		else:
			l.error(f'upload of file {name} FAILED - is not in set of video formats ({k_video_formats}) or image formats ({k_image_formats}) or audio formats ({k_audio_formats})!')
		thumbs.append(name + k_thumb_appendix)
		pos += size

	await hd.ws.send_json({'task': 'files_uploaded', 'reply_type': reply_type, 'path': path, 'names': names, 'thumbs': thumbs})



async def _ws_edit(hd):
	#TODO: SEE TODO items in _ws_drive!
	__send_arrangement_content = lambda a_id, ac_id: _send_arrangement_content(hd, a_id, None, html._content_title_with_edits, True, ac_id)
	match hd.payload['action']:
		case 'arrangement_id': # happens when somebody clicks on a new arrangement (title)
			arrangement_id = int(hd.payload['arrangement_id'])
			await __send_arrangement_content(arrangement_id, None)
		case 'move_composition_down':
			await _move_composition_up_down(hd, 1)
		case 'move_composition_up':
			await _move_composition_up_down(hd, -1)
		case 'insert_composition_before':
			arrangement_id, new_arrangement_composition_id = await db.insert_composition_before(hd.dbc, int(hd.payload['arrangement_composition_id']), int(hd.payload['new_composition_id']))
			await __send_arrangement_content(arrangement_id, new_arrangement_composition_id)
		case 'remove_composition':
			arrangement_id = await db.remove_composition_from_arrangement(hd.dbc, hd.payload['arrangement_composition_id'])
			await __send_arrangement_content(arrangement_id, None)

		case 'insert_new_composition_before':
			arrangement_id, new_arrangement_composition_id = await db.insert_new_composition_before(hd.dbc, int(hd.payload['composition_id']), int(hd.payload['arrangement_composition_id']))
			await __send_arrangement_content(arrangement_id, new_arrangement_composition_id)

		case 'filter_arrangements':
			results = await db.get_compositions_and_arrangements(hd.dbc, hd.payload['strng'])
			result_content = html.build_arrangement_filter_result_content(results, hd.payload['before_production_arrangement_id'])
			await hd.ws.send_json({'task': 'arrangement_filter_results', 'result_content': result_content})

		case 'filter_backgrounds':
			images = await db.get_background_images(hd.dbc, hd.payload['strng'])
			videos = await db.get_background_videos(hd.dbc, hd.payload['strng'])
			result_content = html.build_background_filter_result_content(_origin(hd.rq), images, videos)
			await hd.ws.send_json({'task': 'background_filter_results', 'result_content': result_content})
		case 'set_bg_media':
			result = await db.set_background_media(hd.dbc, int(hd.payload['arrangement_id']), hd.payload['filename'])
			await hd.ws.send_json({'task': 'background_media_result', 'result': result})
			
		case 'set_composition_content':
			acid = int(hd.payload['arrangement_composition_id'])
			aid = await _set_composition_content(hd, acid)
			await __send_arrangement_content(aid, acid)

		case 'fetch_composition_content':
			result = await db.get_flat_composition_content(hd.dbc, int(hd.payload['composition_id']))
			text = ''
			for phrase in result.phrases:
				for contents in phrase.content:
					text += contents['content'] + '\n'
				text += '\n'
			await hd.ws.send_json({'task': 'fetch_composition_content', 'title': result.title, 'text': text, 'content_type': result.content_type})

		case 'insert_arrangement_before':
			production_id, new_pa_id = await db.insert_arrangement_before(hd.dbc, hd.payload['production_arrangement_id'], hd.payload['new_arrangement_id'], hd.payload['typ'])
			await _send_production_content(hd, production_id, None, html._content_title_with_edits, True, new_pa_id)
		case 'remove_arrangement':
			production_id = await db.remove_arrangement_from_production(hd.dbc, hd.payload['production_arrangement_id'])
			await _send_production_content(hd, production_id, None, html._content_title_with_edits, True)
		case 'insert_new_composition_arrangement_before':
			production_id, new_pa_id = await db.insert_new_composition_arrangement_before(hd.dbc, hd.payload['production_arrangement_id'], hd.payload['new_composition_name'])
			await _send_production_content(hd, production_id, None, html._content_title_with_edits, True, new_pa_id)
			

		case 'move_arrangement_down':
			await _move_arrangement_up_down(hd, 1)
		case 'move_arrangement_up':
			await _move_arrangement_up_down(hd, -1)



async def _set_composition_content(hd, acid):
	text = hd.payload['text']

	# TODO!!! HERE -- this is where we can detect json and save as a singleton phrase, rather than breaking into phrases
	phrases = []
	content_lines = []
	for line in text.strip().splitlines():
		stripped_line = line.strip()
		if not stripped_line: # if blank line...
			if content_lines: # multiple blank lines should be ignored, rather than creating extra (empty) phrases
				phrases.append(content_lines)
				content_lines = []
		else:
			content_lines.append(line)
	# final straggler:
	if content_lines:
		phrases.append(content_lines)

	arrangement_id = await db.set_composition_content(hd.dbc, acid, hd.payload['title'], phrases)
	return arrangement_id

async def _move_composition_up_down(hd, up_down):
	ac_id = int(hd.payload['arrangement_composition_id'])
	arrangement_id = await db.move_composition_up_down(hd.dbc, ac_id, up_down)
	await _send_arrangement_content(hd, arrangement_id, None, html._content_title_with_edits, True, ac_id)

async def _move_arrangement_up_down(hd, up_down):
	pa_id = int(hd.payload['production_arrangement_id'])
	production_id = await db.move_arrangement_up_down(hd.dbc, pa_id, up_down)
	await _send_production_content(hd, production_id, None, html._content_title_with_edits, True, pa_id)

async def _send_production_content(hd, production_id, click_script, content_titler, include_available_compositions = False, production_arrangement_id_to_highlight = None):
	arrangement_titles = await db.get_production_arrangement_titles(hd.dbc, production_id)
	if not arrangement_titles:
		arrangement_content = []
	else:
		if production_arrangement_id_to_highlight: 
			arrangement_content = await db.get_production_arrangement_content(hd.dbc, production_arrangement_id_to_highlight)
		else:
			first = arrangement_titles[0] # just use the first arrangement in the production...
			arrangement_content = await db.get_arrangement_content(hd.dbc, first.arrangement_id)
			production_arrangement_id_to_highlight = first.production_arrangement_id

	production_content_div = html.build_left_arrangement_titles(arrangement_titles, 'load_arrangement', True, production_arrangement_id_to_highlight)
	available_compositions = None
	if include_available_compositions and arrangement_content:
		available_compositions = await db.get_available_compositions(hd.dbc, arrangement_content.arrangement_id)
	arrangement_content_div = html.detail_nested_content(_origin(hd.rq), arrangement_content, click_script, content_titler, available_compositions)
	await hd.ws.send_json({'task': 'set_production_and_arrangement_content', 'production_content': production_content_div, 'arrangement_content': arrangement_content_div})

async def _ws_next_auto_advance(hd):
	await drive_forward(hd)

async def _ws_reload_all_watchers(hd):
	for lpi, lp in hd.rq.app['lps'].items():
		await asyncio.gather(*[ws.send_json({'task': 'reload'}) for ws in lp.watchers.keys()])


async def _set_up_common_get_post(request, dbc = True, uuid = True, data = True, re_log_in_seconds = None):
	result = U.Struct(rq = request, session = await get_session(request))
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

async def _set_up_common_get(request, dbc = False, re_log_in_seconds = None):
	return await _set_up_common_get_post(request, dbc, uuid = False, data = False, re_log_in_seconds = re_log_in_seconds)

async def _set_up_common_post(request, dbc = True, uuid = True, data = True, re_log_in_seconds = None):
	return await _set_up_common_get_post(request, dbc, uuid = uuid, data = data, re_log_in_seconds = re_log_in_seconds)


# Init / Shutdown -------------------------------------------------------------

async def _init(app):
	await _init_db(app)
	app['obs_ifs'] = [] #await asyncio.gather(*[ws.send_str('slide_scene') for ws in hd.rq.app['obs_ifs']])
	app['xair_ifs'] = [] #await asyncio.gather(*[ws.send_str('unmute_dp') for ws in hd.rq.app['xair_ifs']])
	app['bg_music_ifs'] = [] #await asyncio.gather(*[ws.send_str('play') for ws in hd.rq.app['bg_music_ifs']])
	app['qlc_ifs'] = [] #await asyncio.gather(*[ws.send_str('restore') for ws in hd.rq.app['qlc_ifs']])

	app['lps'] = {}

async def _shutdown(app):
	l.info('Shutting down...')
	if 'db' in app:
		await app['db'].close()
	for lpi, lp in app['lps'].items():
		for ws in lp.watchers.keys():
			await ws.close()
	l.info('...shutdown complete')


async def _init_db(app):
	l.info('Initializing database...')

	conn = await aiosqlite.connect(settings.db_filename, isolation_level = None, detect_types = PARSE_DECLTYPES) # "isolation_level = None disables the Python wrapper's automatic handling of issuing BEGIN etc. for you. What's left is the underlying C library, which does do "autocommit" by default. That autocommit, however, is disabled when you do a BEGIN (b/c you're signaling a transaction with that statement" - from https://stackoverflow.com/questions/15856976/transactions-with-python-sqlite3 - thanks Thanatos
	conn.row_factory = aiosqlite.Row
	await conn.execute('pragma journal_mode = wal') # see https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/ - since we're using async/await from a wsgi stack, this is appropriate
	await conn.execute('pragma foreign_keys = ON')
	#await conn.execute('pragma case_sensitive_like = true')
	#await conn.set_trace_callback(l.debug) - not needed with aiosqlite, anyway

	app['db'] = conn # consider conn.cursor(), instead, according to more "typical" use; sqlite3 has an "efficient" approach that involves just using the database directly (a temp cursor is auto-created under the hood): https://pysqlite.readthedocs.io/en/latest/sqlite3.html#using-sqlite3-efficiently

	l.info('...database initialized')


# Run server like so, from cli:
#		python -m aiohttp.web -H localhost -P 8080 main:init
#		python -m aiohttp.web -H localhost -P 8462 main:init
#         https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers
# Or, using adev (from parent directory!) (TYPICAL):
#		adev runserver -s static --livereload app
# Or... (older?)
#		adev runserver --app-factory init --livereload --debug-toolbar test1_app
def init(argv):
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

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(description="aiohttp server example")
	parser.add_argument('--path')

	app = app()

	args = parser.parse_args()
	web.run_app(app, path=args.path)#, port=args.port)
