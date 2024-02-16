__author__ = 'J. Michael Caine'
__copyright__ = '2022'
__version__ = '0.1'
__license__ = 'MIT'

from . import util as U

from datetime import datetime

import logging
l = logging.getLogger(__name__)

async def fetchone(dbc, sql_and_args):
	#TODO: sql_and_args[0] += ' limit 1'
	r = await dbc.execute(*sql_and_args)
	return await r.fetchone()

async def fetchall(dbc, sql_and_args):
	r = await dbc.execute(*sql_and_args)
	return await r.fetchall()

_j_composition_title = 'title on title.id = composition.title'
async def _get_compositions_by_tag(dbc, joins, where, args):
	joins = [_j_composition_title] + joins
	return await fetchall(dbc, (f'select composition.id, title.title from composition join {" join ".join(joins)} where {where}', args))

_j_composition_tag = 'composition_tag on composition_tag.composition = composition.id'
async def get_compositions_by_tag(dbc, tag_id):
	joins = [_j_composition_tag]
	where = 'composition_tag.tag = ?'
	args = (tag,)
	return await _get_compositions_by_tag(dbc, joins, where, args)

_j_composition_tag_tag = 'tag on tag.id = composition_tag.tag'
async def get_compositions_by_tag_name(dbc, tag_name):
	joins = [_j_composition_tag, _j_composition_tag_tag]
	where = 'tag.name like ?'
	args = ('%' + tag_name + '%',)
	return await _get_compositions_by_tag(dbc, joins, where, args)



def _synthesize_title(record):
	return record['title'].replace('{composition_title}', record['composition_title'])

_j_arrangement_title = 'title on title.id = arrangement.title'
_j_composition = 'composition on composition.id = arrangement.composition'
_j_composition_title_2 = 'title as composition_title_table on composition_title_table.id = composition.title'
async def _get_arrangements_by_tag(dbc, joins, where, args):
	joins = [_j_arrangement_title, _j_composition, _j_composition_title_2] + joins
	select = 'select arrangement.id, title.title as title, composition_title_table.title as composition_title'
	result = await fetchall(dbc, (f'{select} from arrangement join {" join ".join(joins)} where {where}', args))
	result2 = []
	for r in result:
		result2.append({'id': r['id'], 'title': _synthesize_title(r)})
	return result2

_j_arrangement_tag = 'arrangement_tag on arrangement_tag.arrangement = arrangement.id'
async def get_arrangements_by_tag(dbc, tag_id):
	joins = [_j_arrangement_tag]
	where = 'arrangement_tag.tag = ?'
	args = (tag,)
	return await _get_arrangements_by_tag(dbc, joins, where, args)

_j_arrangement_tag_tag = 'tag on tag.id = arrangement_tag.tag'
async def get_arrangements_by_tag_name(dbc, tag_name):
	joins = [_j_arrangement_tag, _j_arrangement_tag_tag]
	where = 'tag.name like ?'
	args = ('%' + tag_name + '%',)
	return await _get_arrangements_by_tag(dbc, joins, where, args)

async def _get_phrases(dbc, composition_id):
	return [await _get_phrase(dbc, phrase) for phrase in await fetchall(dbc, ('select * from phrase where composition = ? order by seq', (composition_id,)))]

_s_arrangement_basic = 'select arrangement.id as arrangement_id, arrangement.background as background, title.title as title, composition.id as composition_id, composition_title_table.title as composition_title, composition.content_type as content_type'
_js_arrangement_composition_titles = [_j_arrangement_title, _j_composition, _j_composition_title_2]
async def get_arrangement_content(dbc, arrangement_id):
	r = await fetchone(dbc, (f'{_s_arrangement_basic} from arrangement join {" join ".join(_js_arrangement_composition_titles)} where arrangement.id = ?', (arrangement_id,)))
	return U.Struct(
		arrangement_id = arrangement_id,
		composition_id = r['composition_id'],
		content_type = r['content_type'],
		title = _synthesize_title(r),
		background = r['background'],
		phrases = await _get_phrases(dbc, r['composition_id']), # may be empty list []!
		children = [await get_composition_content(dbc, child['composition'], child['id']) for child in await fetchall(dbc, ('select id, composition from arrangement_composition where arrangement = ? order by seq', (r['arrangement_id'],)))],
	)

async def get_production_arrangement_content(dbc, production_arrangement_id):
	# This just fetches the (proper) arrangement_id from the (provided) production_arrangement_id, then calls the real get_arrangement_content...
	return await get_arrangement_content(dbc, (await fetchone(dbc, ('select arrangement from production_arrangements where id = ?', (production_arrangement_id,))))['arrangement'])

async def get_composition_content(dbc, composition_id, arrangement_composition_id = None):
	c = await fetchone(dbc, ('select composition.global, composition.content_type, title.title from composition join title on title.id = composition.title where composition.id = ?', (composition_id,)))
	return U.Struct(
		arrangement_composition_id = arrangement_composition_id,
		composition_id = composition_id,
		content_type = c['content_type'],
		title = c['title'],
		globl = c['global'],
		phrases = await _get_phrases(dbc, composition_id), # may be empty list []!
		children = [await get_composition_content(dbc, child['id']) for child in await fetchall(dbc, ('select id from composition where parent = ? order by seq', (composition_id,)))], # may be empty list []!
	)

#async def get_content(dbc, composition_id):
#	return await fetchall(dbc, ('select id, content from content where composition = ? order by seq', (composition_id,)))

async def _get_phrase(dbc, phrase):
	return U.Struct(
		phrase = phrase,
		content = await fetchall(dbc, ('select * from content where phrase = ? order by seq', (phrase['id'],))),
	)

async def get_phrase(dbc, phrase_id):
	return await _get_phrase(dbc, await fetchone(dbc, ('select * from phrase where id = ?', (phrase_id,))))

async def get_composition_first_phrase(dbc, composition_id):
	#return await fetchone(dbc, ('select * from phrase join composition on composition.id = phrase.composition where composition.parent = ? order by composition.seq, phrase.seq', (composition_id,)))
	return await _get_phrase(dbc, await fetchone(dbc, ('select * from phrase where composition = ? order by phrase.seq', (composition_id,))))

async def get_production_arrangement_titles(dbc, production_id):
	joins = _js_arrangement_composition_titles + ['production_arrangements on production_arrangements.arrangement = arrangement.id',]
	arrangements = await fetchall(dbc, (f'{_s_arrangement_basic}, production_arrangements.id as production_arrangement_id from arrangement join {" join ".join(joins)} where production_arrangements.production = ? order by production_arrangements.seq', (production_id,)))
	return [U.Struct(
		production_arrangement_id = a['production_arrangement_id'],
		arrangement_id = a['arrangement_id'],
		composition_id = a['composition_id'],
		title = _synthesize_title(a),
	) for a in arrangements]
	

async def _fetch_nearest_production_id(dbc):
	p = await fetchone(dbc, ("select id from production order by abs(strftime('%s', production.scheduled) - strftime('%s', ?)) limit 1", (datetime.now().isoformat(),)))
	return p['id']
	
	
async def start_or_join_live_production(dbc, production_id):
	if production_id == 0: # signal: "just fetch the 'nearest' one!"
		production_id = await _fetch_nearest_production_id(dbc)
	arrangement_titles = await get_production_arrangement_titles(dbc, production_id)
	lpi_id = await fetchone(dbc, ('select * from live_production_index where production = ?', (production_id, )))
	if lpi_id:
		lpi_id = lpi_id['id']
	if not lpi_id:
		# TODO: the line below fails, within get_composition_first_phrase() (actually, within the ()get_phrase() call therein), due to an erroneous composition_id; can't figure it out now; am fudging this to 8, 1 (two lines below) because it doesn't really matter at the moment.
		#r = await dbc.execute('insert into live_production_index (production, arrangement, phrase) values (?, ?, ?)', (production_id, arrangement_titles[0].arrangement_id, (await get_composition_first_phrase(dbc, arrangement_titles[0].composition_id))['id']))
		r = await dbc.execute('insert into live_production_index (production, arrangement, phrase) values (?, 8, 1)', (production_id,))
		lpi_id = r.lastrowid
	#OLD; REMOVE! arrangement = await fetchone(dbc, ('select arrangement.id from arrangement join production_arrangements on arrangement.id = production_arrangements.arrangement where production = ? order by production_arrangements.seq limit 1', (production_id,)))
	arrangement_id = arrangement_titles[0].arrangement_id

	return U.Struct(
		production = await fetchone(dbc, ('select * from production where id = ?', (production_id,))),
		arrangement_titles = arrangement_titles,
		first_arrangement_content = await get_arrangement_content(dbc, arrangement_id),
		lpi_id = lpi_id,
	)
		
async def get_live_production_live_content(dbc, lpi_id):
	lpi = await fetchone(dbc, ('select * from live_production_index where id = ?', (lpi_id, )))
	return await get_phrase(dbc, lpi['phrase'])

async def advance_live_production(dbc, lpi_id):
	pass
	
#async def get_live_production_queued_next_content(dbc, lpi_id):
#async def get_live_production_queued_after_content(dbc, lpi_id):

async def create_production(dbc, name, scheduled_date, template_id = None):
	r = await dbc.execute('insert into production (name, scheduled, location) values (?, ?, ?)', (name, scheduled_date, 1))
	pid = r.lastrowid
	if template_id:
		pas = await fetchall(dbc, ('select * from production_arrangements where production = ?', (template_id,)))
		r = await dbc.executemany('insert into production_arrangements (production, arrangement, seq) values (?, ?, ?)', [(pid, p['arrangement'], p['seq']) for p in pas])
		await dbc.commit() #TODO necessary?!
	return pid

async def edit_production(dbc, pid, name, scheduled_date):
	r = await dbc.execute(f'update production set name = ?, scheduled = ? where id = ?', (name, scheduled_date, pid))
	assert (r.rowcount == 1) # TODO: raise exception in production, too

async def get_coming_productions(dbc, limit = 5):
	#TODO: filter for 'location'!
	return await fetchall(dbc, ('select * from production where scheduled > ? order by scheduled limit ?', (datetime.now().isoformat(), limit)))

async def get_production(dbc, production_id):
	return await fetchone(dbc, ('select * from production where id = ?', (production_id,)))

async def get_production_templates(dbc):
	return await fetchall(dbc, ('select * from production where template is not null order by template', ()))

async def _move_up_down(dbc, _id, up_down, table, field):
	# Get the record to be moved up or down:
	rec = await fetchone(dbc, (f'select * from {table} where id = ?', (_id,)))
	if up_down == -1:
		other_rec = await fetchone(dbc, (f'select * from {table} where {field} = {rec[field]} and seq < {rec["seq"]} order by seq desc limit 1', ()))
	else:
		assert(up_down == 1)
		other_rec = await fetchone(dbc, (f'select * from {table} where {field} = {rec[field]} and seq > {rec["seq"]} order by seq asc limit 1', ()))
	if other_rec:
		# Swap the seq values (note, seq values are FLOATs - they may take on fractional values; for instance, when a record is "inserted", in sequence, it will often get a float-point number between the records below and above; therefore, we have to swap seqs rather than just, e.g., adding and subtracting one from each):
		r = await dbc.execute(f'update {table} set seq = {other_rec["seq"]} where id = ?', (_id,))
		assert(r.rowcount == 1) # TODO: raise exception in production, too
		r = await dbc.execute(f'update {table} set seq = {rec["seq"]} where id = ?', (other_rec['id'],))
		assert(r.rowcount == 1) # TODO: raise exception in production, too
	# Return the [field] value of this moved record; it's useful to callers
	return rec[field]
	
async def move_composition_up_down(dbc, arrangement_composition_id, up_down): # up_down = -1 to move up; +1 to move down (higher sequence numbers mean further down in the order)
	return await _move_up_down(dbc, arrangement_composition_id, up_down, 'arrangement_composition', 'arrangement')
	# this returns the arrangement_id to which this moved composition belongs, which is useful to callers (e.g., to re-load that arrangement, now that the move is complete)

async def move_arrangement_up_down(dbc, production_arrangement_id, up_down): # up_down = -1 to move up; +1 to move down (higher sequence numbers mean further down in the order)
	return await _move_up_down(dbc, production_arrangement_id, up_down, 'production_arrangements', 'production')
	# this returns the production_id to which this moved arrangement belongs, which is useful to callers (e.g., to re-load that arrangement, now that the move is complete)

async def _insert_X_before(dbc, table, pkid, match_field):
	r = await fetchone(dbc, (f'select * from {table} where id = ?', (pkid,)))
	rec_before = await fetchone(dbc, (f'select * from {table} where {match_field} = ? and seq < ? order by seq desc limit 1', (r[match_field], r['seq'])))
	if rec_before:
		new_seq = (r['seq'] + rec_before['seq']) / 2
	else:
		new_seq = r['seq'] / 2
	return r, new_seq

async def insert_arrangement_before(dbc, production_arrangement_id, new_arrangement_id, typ, content_type = None):
	if typ == 'composition':
		# First, fabricate the new arrangement (`new_arrangement_id` is actually a composition id in this case!):
		r = await dbc.execute('insert into arrangement (title, composition, content_type) values (?, ?, ?)', (812, new_arrangement_id, content_type)) # TODO: 1) replace '812' hardcode! 2) add background!?
		new_arrangement_id = r.lastrowid
		# Add a final "blank" as the last TODO: KLUDGY!?
		await dbc.execute('insert into arrangement_composition(arrangement, composition, seq) values (?, ?, 1000)', (new_arrangement_id, 2833)) # TODO replace 2833 hardcode! AND 100 hardcode!

	pa, new_seq = await _insert_X_before(dbc, 'production_arrangements', production_arrangement_id, 'production')
	r = await dbc.execute('insert into production_arrangements (production, arrangement, seq) values (?, ?, ?)', (pa['production'], new_arrangement_id, new_seq))
	new_production_arrangement_id = r.lastrowid
	return pa['production'], new_production_arrangement_id

async def insert_composition_before(dbc, arrangement_composition_id, new_composition_id): # TODO: see many similarities in insert_arrangement_before() - combine code!
	ac, new_seq = await _insert_X_before(dbc, 'arrangement_composition', arrangement_composition_id, 'arrangement')
	r = await dbc.execute('insert into arrangement_composition (arrangement, composition, seq) values (?, ?, ?)', (ac['arrangement'], new_composition_id, new_seq))
	new_arrangement_composition_id = r.lastrowid
	return ac['arrangement'], new_arrangement_composition_id

async def insert_new_composition_before(dbc, composition_id, arrangement_composition_id):
	r = await dbc.execute('insert into title (title) values (?)', ('NEW!',)) # editable later...
	title_id = r.lastrowid
	ct = (await fetchone(dbc, ('select content_type from composition where id = ?', (composition_id,))))['content_type']
	r = await dbc.execute('insert into composition (title, parent, seq, content_type) values (?, ?, ?, ?)', (title_id, composition_id, 100, ct)) # TODO: '100' is bogus; should discover what last is, and +1
	return await insert_composition_before(dbc, arrangement_composition_id, r.lastrowid)

async def insert_new_composition_arrangement_before(dbc, production_arrangement_id, new_composition_name, content_type = None):
	# this is for a new SONG, or "titled" (top-level) composition; many references to "composition" are to building-block compositions
	r = await dbc.execute('insert into title (title) values (?)', (new_composition_name,))
	title_id = r.lastrowid
	r = await dbc.execute('insert into composition (title, content_type) values (?, ?)', (title_id, ct))
	composition_id = r.lastrowid
	r = await dbc.execute('insert into composition_tag (composition, tag) values (?, ?)', (composition_id, 2)) # TODO: '2' is a hardcode record ID for "song" - fix/generalize!
	return await insert_arrangement_before(dbc, production_arrangement_id, composition_id, 'composition', content_type)


async def remove_composition_from_arrangement(dbc, arrangement_composition_id):
	ac = await fetchone(dbc, ('select arrangement from arrangement_composition where id = ?', (arrangement_composition_id,)))
	await dbc.execute(f'delete from arrangement_composition where id = ?', (arrangement_composition_id,))
	return ac['arrangement']

async def remove_arrangement_from_production(dbc, production_arrangement_id):
	pa = await fetchone(dbc, ('select production from production_arrangements where id = ?', (production_arrangement_id,)))
	await dbc.execute('delete from production_arrangements where id = ?', (production_arrangement_id,))
	return pa['production']

async def get_available_compositions(dbc, arrangement_id):
	compositions = await fetchall(dbc, ('select composition.id, title.title as title from composition join arrangement on parent = arrangement.composition join title on composition.title = title.id where arrangement.id = ? order by seq', (arrangement_id,)))
	result = [(c['title'], c['id']) for c in compositions]
	result.append(('<blank>', 2833)) # TODO replace 2833 hardcode!
	return result

async def get_compositions_and_arrangements(dbc, strng):
	joins = [_j_arrangement_title, _j_composition, _j_composition_title_2]
	select = 'select arrangement.id, title.title as title, composition_title_table.title as composition_title'
	like_string = f'%{strng}%'
	final = []
	for r in await fetchall(dbc, (f'{select} from arrangement join {" join ".join(joins)} where (title.title like ? or composition_title like ?) order by composition_title limit 7', (like_string, like_string, ))):
		final.append({'id': r['id'], 'title': _synthesize_title(r), 'typ': 'arrangement'})
	for r in await fetchall(dbc, ('select composition.id, title.title as title from composition join title on composition.title = title.id where composition.parent is NULL and title.title like ? limit 7', (like_string,))):
		final.append({'id': r['id'], 'title': r['title'] + ' - NEW', 'typ': 'composition'})
	final.sort(key = lambda i: i['title'])
	return final

from os import listdir, getcwd
from os.path import isfile, join
async def get_background_images(dbc, strng):
	return _get_background_x(dbc, strng, join(getcwd(), 'static', 'bgs'))

async def get_background_videos(dbc, strng):
	return _get_background_x(dbc, strng, join(getcwd(), 'static', 'bgs', 'videos'))

def _get_background_x(dbc, strng, path):
	return [U.Struct(
		filename = f,
	) for f in listdir(path) if (isfile(join(path, f)) and f.endswith('.small.jpg'))]  # filtering on .jpg even for videos, as we want the thumbnails....

async def set_background_media(dbc, arrangement_id, filename):
	r = await dbc.execute(f'update arrangement set background = ? where id = ?', (filename, arrangement_id))
	return r.rowcount == 1

async def set_composition_content(dbc, arrangement_composition_id, title, phrases):
	# TODO: do this whole function as a transaction, which we can roll back if something goes wrong....
	ac = await fetchone(dbc, ('select arrangement_composition.*, composition.title as title from arrangement_composition join composition on arrangement_composition.composition = composition.id where arrangement_composition.id = ?', (arrangement_composition_id,)))
	composition_id = ac['composition']
	await dbc.execute('update title set title = ? where id = ?', (title, ac['title'])) # TODO: check result?!
	await dbc.execute('delete from phrase where composition = ?', (composition_id,)) # TODO: just MARK as deleted, in DB, instead, to make for easy "undo"?!

	phrase_seq = 0
	for phrase in phrases:
		phrase_seq += 1
		r = await dbc.execute('insert into phrase (composition, seq, display_scheme) values (?, ?, ?)', (composition_id, phrase_seq, 1))
		phrase_id = r.lastrowid
		assert(phrase_id)
		content_seq = 0
		for line in phrase:
			content_seq += 1
			await dbc.execute('insert into content (phrase, content, seq) values (?, ?, ?)', (phrase_id, line, content_seq))
	#!!!dbc.commit()
	
	return ac['arrangement']

async def get_flat_composition_content(dbc, composition_id):
	r = await fetchone(dbc, ('select title.title, composition.content_type from title join composition on title.id = composition.title where composition.id = ?', (composition_id,)))
	return U.Struct(
		title = r['title'],
		content_type = r['content_type'],
		phrases = await _get_phrases(dbc, composition_id),
	)

_get_x_phrase = lambda comparator, desc_asc: f'select * from phrase join composition on composition.id = phrase.composition join arrangement_composition on arrangement_composition.composition = composition.id where arrangement_composition.id = ? and phrase.seq {comparator} (select seq from phrase where id = ?) order by seq {desc_asc} limit 1'

async def get_next_phrase(dbc, ac_id, phrase_id):
	result = await fetchone(dbc, (_get_x_phrase('>', 'asc'), (ac_id, phrase_id)))
	return result['id'] if result else None

async def get_previous_phrase(dbc, ac_id, phrase_id):
	result = await fetchone(dbc, (_get_x_phrase('<', 'desc'), (ac_id, phrase_id)))
	return result['id'] if result else None

