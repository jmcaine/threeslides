
import logging
import asyncio

from pandora import clientbuilder
from pydora.audio_backend import VLCPlayer
from pydora.utils import iterate_forever
import vlc

l = logging.getLogger(__name__)

playlist = None
media = None

def start():
	l.debug(f'PANDORA --- start()ing')
	client = clientbuilder.SettingsDictBuilder({
		"DECRYPTION_KEY": 'R=U!LH$O2B#',
		"ENCRYPTION_KEY": '6#26FRL$ZWD',
		"PARTNER_USER": 'android',
		"PARTNER_PASSWORD": 'AC7IBG09A3DTSYM4R41UJWL07VLN8JI7',
		"DEVICE": 'android-generic',
	}).build()
	client.login('nospam4@doubleserver.com', 'stonehenge')
	station = client.get_station('3857512263910053953') # Praise and Worship Radio

	global playlist
	playlist = station.get_playlist()
	l.debug(f'PANDORA --- got playlist')


def play_next():
	song = next(playlist)
	#l.debug(f'PANDORA --- song: {song.song_name}, url: {song.audio_url}')
	song.prepare_playback()
	global media
	media = vlc.MediaPlayer(song.audio_url)
	duration = song.track_length #media.get_length()
	media.play()
	return duration


def stop():
	global media
	if media:
		media.stop()

'''
from app import pandora_player
pandora_player.start()

import importlib
importlib.reload(pandora_player)

'''
