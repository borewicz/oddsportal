# -*- coding: utf-8 -*-
import requests
import re
import json
from info import betting_types, bookmakers, leagues
import time
import sys
import os


def unhash(xhash):
    decoded = ''
    for i in xhash.split('%')[1:]:
        decoded += chr(int(i, 16))
    return decoded


version_id = 1
sport_id = 1
scope_ids = {
    2, 3, 4,  # full, 1st half, 2nd half
}

s = requests.Session()


def get_match(match):
    page = s.get('http://www.oddsportal.com/a/b/c/d-%s/' % match['match_id'])
    # match_id = re.findall(r'id":"([^"]+)"', page.text)[0]
    xhash = unhash(re.findall(r'xhashf":"([^"]+)"', page.text)[0])
    # xhashf = unhash(re.findall(r'xhashf":"([^"]+)"', page.text)[0])
    score_result = s.get('http://fb.oddsportal.com/feed/postmatchscore/' +
                         '%d-%s-%s.dat' % (
                             sport_id,
                             match['match_id'],
                             xhash),
                         ).text
    # print(score_result)
    score_data = re.findall(r'[0-9]+:[0-9]+', score_result)

    match['odds'] = {
        2: {},
        3: {},
        4: {},
    }
    if score_data:
        match['score'] = score_data[0]
        match['status'] = 'finished'
        if len(score_data[:1]) > 0:
            match['partial'] = score_data[1:]
    else:
        try:
            match['status'] = re.findall(r'>([^>]+)<', score_result)[0]
        except:
            # jeżeli result = "", to mecz się jeszcze nie odbył
            pass

    for betting_type in betting_types:
        for scope_id in scope_ids:
            # try:
            r = s.get('http://fb.oddsportal.com/feed/match/' +
                      '%d-%d-%s-%d-%d-%s.dat' % (
                          version_id,
                          sport_id,
                          match['match_id'],
                          betting_type,
                          scope_id,
                          xhash,
                      ))
            # regex = re.findall(r' ([^)]+)', r.text)[0]
            regex = re.findall(r' ([^$]+)\)', r.text)[0]
            data = json.loads(regex)
            bets = data['d']['oddsdata']['back']
            if bets:
                for bet in bets:
                    # for item in bet['odds']:
                    for bookmaker in bookmakers:
                        if bookmaker in bets[bet]['odds']:
                            bets[bet]['odds'][bookmakers[bookmaker]] = bets[bet]['odds'].pop(bookmaker)
                    # print(json.dumps(bets[bet]))
                    if betting_types[betting_type] not in match['odds'][scope_id]:
                        match['odds'][scope_id][betting_types[betting_type]] = {}
                    if 'mixedParameterName' in bets[bet]:
                        match['odds'][scope_id][betting_types[betting_type]][bets[bet]['mixedParameterName']] = \
                            bets[bet]['odds']
                    else:
                        match['odds'][scope_id][betting_types[betting_type]][bets[bet]['handicapValue']] = \
                            bets[bet]['odds']
            # except:
            #     with open('to_reget.dat', 'a+') as f:
            #         f.write(match['match_id'] + '\n')


    # na końcu przemianowujemy, bo fajnie jest wtedy
    match['odds']['full_time'] = match['odds'].pop(2)
    match['odds']['first_half'] = match['odds'].pop(3)
    match['odds']['second_half'] = match['odds'].pop(4)
    return match


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        # match = json.load(data_file)
        matches = f.readlines()
    swp = open(sys.argv[1] + ".new", 'a+')
    for match in matches:
        match = get_match(json.loads(match))
        print(json.dumps(match))
        swp.write(json.dumps(match))
    swp.close()
