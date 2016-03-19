import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'betmanager.settings'

import get
import parse
import sys
import json

filename = get.get_matches(int(sys.argv[1]))
print(filename)
with open(filename) as f:
    lines = f.readlines()
for line in lines:
    result = json.loads(line)
    parse.parse_json(result)
