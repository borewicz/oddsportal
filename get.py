import requests
import re
import json
from lxml import html
import match as match_dl
import errno
import os
import sys
import datetime
import parse

s = requests.Session()

timezone_offset = 1
sport = 'soccer'
sport_id = 1
table_type = 2  # 1 - kick off time, 2 - events

reget_file = 'to_reget.dat'


def utilize_link(link):
    link = link.split('/')
    del link[-2]
    return '/'.join(link)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def unhash(xhash):
    decoded = ''
    for i in xhash.split('%')[1:]:
        decoded += chr(int(i, 16))
    return decoded


def build_match(tr):
    match = {
        'match_id': tr.attrib['xeid']
    }
    match = match_dl.get_match(match)
    date = tr.xpath('td[1]')[0]
    match['date'] = re.findall(r' t([^-]+)', date.attrib['class'])[0]
    name = tr.xpath('.//a[not(@id)]')[0].text_content().split(' - ')
    match['home'] = name[0]
    match['away'] = name[1]
    # match['event'] = leagues[i][1:-1]
    event_request = requests.get('http://www.soccer24.com/match/' + match['match_id'])
    event_tree = html.fromstring(event_request.text)
    phrases = event_tree.xpath('//table[@class="detail"]//a/text()')[0].split(' - ')[1:]
    match['event'] = phrases[::-1]
    return match


def get_xhash(date):
    page = s.get('http://www.oddsportal.com/matches/%s/%s' %
                 (sport, date))
    return unhash(re.findall(r'%s":"([^"]+)"' % date, page.text)[1])


def get_league_info(link):
    with open('leagues.json') as f:
        leagues = json.load(f)
    for league in leagues:
        if utilize_link(link).endswith(league[0].replace('results', '')):
            return league
    return []


def get_season(league, link):
    for item in league[4]:
        if item[2] in utilize_link(link):
            return item[1]


def get_matches(offset=0):
    date = datetime.datetime.today() + datetime.timedelta(days=offset)
    date = date.strftime("%Y%m%d")
    f = open('data/%s.json' % date, 'w+')
    xhash = get_xhash(date)
    r = s.get('http://fb.oddsportal.com/ajax-next-games/%d/%d/%d/%s/%s.dat' % (
        sport_id,
        timezone_offset,
        table_type,
        date,
        xhash
    ))
    data = json.loads(re.findall(r' ([^$]+)\)', r.text)[0])
    tree = html.fromstring(data['d'])
    for tr in tree.xpath('//tr[@xeid]'):
        link = tr.xpath('.//a[not(@id)]')[0]
        league = get_league_info(link.attrib['href'])
        if league:
            try:
                match = build_match(tr)
                match['event'] = league[1:-1] + \
                                 [get_season(league, link.attrib['href'])] + \
                                 match['event']
                f.write(json.dumps(match) + '\n')
                # print(json.dumps(match) + '\n')
            except:
                fail = open("to_reget.dat", 'a+')
                fail.write(tr.attrib['xeid'] + '\n')
                fail.close()
    f.close()
    return 'data/%s.json' % date


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

        league = get_league_info(r.url)

        # match['event'] = get_league_info(r.url)[1:]
        event_request = requests.get(
            'http://www.soccer24.com/match/' + match['match_id'])
        event_tree = html.fromstring(event_request.text)
        phrases = event_tree.xpath(
            '//table[@class="detail"]//a/text()')[0].split(' - ')[1:]
        # match['event'] += phrases[::-1]

        match['event'] = league[1:-1] + \
        [get_season(league, r.url)] + \
        phrases[::-1]

        f.write(json.dumps(match) + '\n')
        # print(json.dumps(match) + '\n')
    except:
        fail = open("to_reget.dat", 'a+')
        fail.write(match_id + '\n')
        fail.close()
    f.close()


if __name__ == "__main__":
    mkdir_p('data')
    if sys.argv[1] == 'retry':
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
    else:
        get_matches(int(sys.argv[1]))

