import sys
import logging
logging.basicConfig(level=logging.DEBUG)
sys.path.append('f:\\Project_Ember')
from ember_engine import EmberCore
import asyncio
import ollama

engine = EmberCore()
print('Starting generation...')
stream = engine.generate_mixed_stream('Hello Ember, just testing!', None, None)
try:
    for chunk in stream:
        print('CHUNK:', chunk)
except Exception as e:
    print('ERROR:', e)
print('Done!')
