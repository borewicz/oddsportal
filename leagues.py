import requests
import re
import json
from info import leagues
from lxml import html

s = requests.Session()

for league in leagues:
    page = s.get('http://www.oddsportal.com/soccer' + league[0])
    tree = html.fromstring(page.text)
    i = 0
    ids = []
    for a in tree.xpath('//ul[@class="main-filter"]//a'):
        if 'results' in a.attrib['href']:
            result = s.get('http://www.oddsportal.com' + a.attrib['href'])
            id = re.findall(r'id":"([^"]+)"', result.text)[0]
            t = html.fromstring(result.text)
            season = t.xpath('//div[@class="main-menu2 main-menu-gray"]//span[@class="active"]//a')[0].text_content()
            beka = [id, season, a.attrib['href'].replace('/results/', '')]
            if beka not in ids:
               ids.append(beka)
            print(a.attrib['href'].replace('/results/', ''))
    league.append(ids)
print(json.dumps(leagues))
