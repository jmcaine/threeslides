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

_s_arrangement_basic = 'select arrangement.id as arrangement_id, arrangement.background as background, title.title as title, composition.id as composition_id, composition_title_table.title as composition_title'
_js_arrangement_composition_titles = [_j_arrangement_title, _j_composition, _j_composition_title_2]
async def get_arrangement_content(dbc, arrangement_id):
	arrangement = await fetchone(dbc, (f'{_s_arrangement_basic} from arrangement join {" join ".join(_js_arrangement_composition_titles)} where arrangement.id = ?', (arrangement_id,)))
	return U.Struct(
		composition_id = arrangement['composition_id'],
		title = _synthesize_title(arrangement),
		background = arrangement['background'],
		phrases = await _get_phrases(dbc, arrangement['composition_id']), # may be empty list []!
		children = [await get_composition_content(dbc, child['composition'], child['id']) for child in await fetchall(dbc, ('select id, composition from arrangement_composition where arrangement = ? order by seq', (arrangement['arrangement_id'],)))],
	)

async def get_production_arrangement_content(dbc, production_arrangement_id):
	# This just fetches the (proper) arrangement_id from the (provided) production_arrangement_id, then calls the real get_arrangement_content...
	return await get_arrangement_content(dbc, (await fetchone(dbc, ('select arrangement from production_arrangements where id = ?', (production_arrangement_id,))))['arrangement'])

async def get_composition_content(dbc, composition_id, arrangement_composition_id = None):
	return U.Struct(
		arrangement_composition_id = arrangement_composition_id,
		composition_id = composition_id,
		title = (await fetchone(dbc, ('select title.title from composition join title on title.id = composition.title where composition.id = ?', (composition_id,))))['title'],
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
	

async def start_or_join_live_production(dbc, production_id):
	arrangement_titles = await get_production_arrangement_titles(dbc, production_id)
	lpi_id = await fetchone(dbc, ('select * from live_production_index where production = ?', (production_id, )))
	if lpi_id:
		lpi_id = lpi_id['id']
	if not lpi_id:
		r = await dbc.execute('insert into live_production_index (production, arrangement, phrase) values (?, ?, ?)', (production_id, arrangement_titles[0].arrangement_id, (await get_composition_first_phrase(dbc, arrangement_titles[0].composition_id))['id']))
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

async def create_production(dbc, name, scheduled_date):
	r = await dbc.execute('insert into production (name, scheduled, location) values (?, ?, ?)', (name, scheduled_date, 1))
	return r.lastrowid

async def get_coming_productions(dbc, limit = 5):
	#TODO: filter for 'location'!
	return await fetchall(dbc, ('select * from production where scheduled > ? order by scheduled limit ?', (datetime.now().isoformat(), limit)))

async def get_production(dbc, production_id):
	return await fetchone(dbc, ('select * from production where id = ?', (production_id,)))

async def _move_up_down(dbc, _id, up_down, table, field):
	# Get the record to be moved up or down:
	rec = await fetchone(dbc, (f'select * from {table} where id = ?', (_id,)))
	# First try to move "down" the record that is "above" (or "up" the record that is "below") (Note: this will properly fail if there is no such record above or below)
	r = await dbc.execute(f'update {table} set seq = seq+{-up_down} where {field} = ? and seq = ?', (rec[field], rec['seq'] + up_down))
	if r.rowcount != 0: # rowcount will be 0 if there was no record "above", and we're trying to move "up" (or if there was no record "below" and we're trying to move "down")
		assert(r.rowcount == 1) # btw
		# Now, go ahead and update the record itself, pushing it up (or down):
		r = await dbc.execute(f'update {table} set seq = seq+{up_down} where id = ?', (_id,))
		assert(r.rowcount == 1)
	# Return the _id to which this moved record belongs; it's useful to callers
	return rec[field]
	
async def move_composition_up_down(dbc, arrangement_composition_id, up_down): # up_down = -1 to move up; +1 to move down (higher sequence numbers mean further down in the order)
	return await _move_up_down(dbc, arrangement_composition_id, up_down, 'arrangement_composition', 'arrangement')
	# this returns the arrangement_id to which this moved composition belongs, which is useful to callers (e.g., to re-load that arrangement, now that the move is complete)

async def move_arrangement_up_down(dbc, production_arrangement_id, up_down): # up_down = -1 to move up; +1 to move down (higher sequence numbers mean further down in the order)
	return await _move_up_down(dbc, production_arrangement_id, up_down, 'production_arrangements', 'production')
	# this returns the production_id to which this moved arrangement belongs, which is useful to callers (e.g., to re-load that arrangement, now that the move is complete)
