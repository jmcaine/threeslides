__author__ = 'J. Michael Caine'
__copyright__ = '2022'
__version__ = '0.1'
__license__ = 'MIT'

class Struct:
	def __init__(self, **kwargs):
		for name, value in kwargs.items():
			self.__setattr__(name, value)
			
	def asdict(self):
		return self.__dict__

class KVPair:
	def __init__(self, key, value):
		self.key = key
		self.value = value

tag_it = lambda field_name, tag: field_name + '_' + str(tag)
