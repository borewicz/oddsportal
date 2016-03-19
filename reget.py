import requests
import re
import json
from lxml import html
import match as match_dl
import errno
import os
import sys
from info import leagues
import parse

s = requests.Session()

sid = 1
bookie_hash = 'X0'
use_premium = 1  # xD
timezone_offset = 1

reget_file = 'to_reget.dat'


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def get_league_info(link):
    for league in leagues:
        if league[0].replace('/results', '') in link:
            return league
    return []


def get_match(match_id):
    f = open("data/reget.json", "a+")
    r = s.get('http://www.oddsportal.com/a/b/c/d-%s/' % match_id)
    tree = html.fromstring(r.text)
    try:
        match = {
            'match_id': match_id
        }
        print(match_id)
        match = match_dl.get_match(match)
        name = tree.xpath(
            '//div[@id="col-content"]/h1')[0].text_content().split(' - ')
        match['home'] = name[0]
        match['away'] = name[1]
        match['event'] = get_league_info(r.url)[1:]
        event_request = requests.get(
            'http://www.soccer24.com/match/' + match['match_id'])
        event_tree = html.fromstring(event_request.text)
        phrases = event_tree.xpath(
            '//table[@class="detail"]//a/text()')[0].split(' - ')[1:]
        match['event'] += phrases[::-1]
        f.write(json.dumps(match) + '\n')
    except:
        fail = open("to_reget.dat", 'a+')
        fail.write(match_id + '\n')
        fail.close()
    f.close()


if __name__ == "__main__":
    if os.path.exists(reget_file):
        os.rename(reget_file, reget_file + '.swp')
        with open(reget_file + '.swp') as f:
            for line in f.readlines():
                get_match(line.replace('\n', ''))
        os.remove(reget_file + '.swp')
        with open('data/reget.json') as reget:
            for line in reget.readlines():
                json_data = json.loads(line)
                parse.parse_json(json_data)
        os.remove('data/reget.json')
