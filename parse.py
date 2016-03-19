import django
from django.db import transaction
import re
import sys
from datetime import datetime
import pytz
from info import bookmakers
# sys.path.append('../')

from football.models import *
import json

django.setup()

states = {
    "finished": Match.OK,
    "The match has already started.": Match.INPLAY,
    "Awarded": Match.WO,
    "Canceled": Match.CANCELED,
    "postponed": Match.POSTPONED
}


def get_status(json_status):
    if json_status in states:
        return states[json_status]
    else:
        return Match.WARNING


@transaction.atomic
def parse_json(result):
    match_id = result['match_id']
    if Match.objects.filter(external_id=match_id):
        match = Match.objects.get(external_id=match_id)
    else:
        match = Match()
    # ja pierdole, czemu external_id
    # ale i tak nie zmieniam, nie chce mi się migracji robić xD
    print("%s - %s (%s)" % (result['home'], result['away'], result['match_id']))
    country = Country.objects.get_or_create(name=result['event'][0])[0]
    home = Team.objects.get_or_create(name=result['home'].replace(u'\xa0', u' ').strip(),
                                      country=country)[0]
    away = Team.objects.get_or_create(name=result['away'].replace(u'\xa0', u' ').strip(),
                                      country=country)[0]
    if 'status' in result:
        status = get_status(result['status'])
    else:
        status = Match.FUTURE

    name = result['event'][1]
    try:
        season = result['event'][3]
    except:
        season = '?'
    stage = ''
    importance = result['event'][2]
    league = League.objects.get_or_create(name=name,
                                          country=country,
                                          importance=importance)[0]

    match_round = 0

    try:
        if result['event'][3]:
            if 'Round' in result['event'][4]:
                match_round = int(re.search('\d+', result['event'][3]).group(0))
            else:
                stage = result['event'][4]
    except:
        pass

    match.home = home
    match.away = away
    if 'date' in result:
        date = pytz.timezone('Europe/Warsaw').localize(datetime.fromtimestamp(int(result['date'])))
        match.date = date
    match.external_id = match_id
    match.league = league
    match.stage = stage
    match.round = match_round
    match.season = season
    match.status = status

    try:
        match.save()
    except:
        return

    def get_score(score):
        try:
            return re.findall('\d+', score)
        except:
            return None

    if 'score' in result:
        score = get_score(result['score'])
        if score:
            match.score = Score.objects.create(home=score[0],
                                               away=score[1])

    if 'partial' in result and result['partial']:
        half_score = get_score(result['partial'][0])
        match.half_score = Score.objects.create(home=half_score[0],
                                                away=half_score[1])
        if len(result['partial']) < 2:
            for score in result['partial'][2:]:
                partial = get_score(score)
                match.additional_scores.all().delete()
                if partial:
                    match.additional_scores.add(Score.objects.create(home=partial[0],
                                                                     away=partial[1]))

    match.save()

    simple_bets = ['1x2', 'dc', 'draw no bet', 'odd/even', 'both teams to score']

    betting_types = [
        '1x2',
        'over under',
        'odd/even',
        'draw no bet',
        'dc',
        'both teams to score',
        'asian',
        'correct score',
        'ht/ft',
        'euro handicap'
    ]

    for bookmaker in bookmakers.values():
        name = Bookmaker.objects.get_or_create(name=bookmaker)[0]
        football_bet = FootballBet.objects.get_or_create(match=match,
                                                         bookmaker=name)[0]
        # tu czyścimy wszystkie betsy
        # METODĄ ŻYDOWSKĄ SKURWYSYNY
        for field in football_bet._meta.get_fields(include_hidden=True):
            if any(x in field.name for x in ['_M', '_1hf', '_2hf']) \
                    and '+' not in field.name:
                ret = getattr(football_bet, field.name)
                if ret:
                    try:
                        ret.all().delete()
                    except AttributeError:
                        # ret.delete()
                        # ret.save()
                        pass
        football_bet.save()
        for period in ['full_time', 'first_half', 'second_half']:
            for betting_type in betting_types:
                # try:
                if betting_type in simple_bets:
                    if betting_type in result['odds'][period] \
                            and bookmaker in result['odds'][period][betting_type]['0.00']:
                        val = result['odds'][period][betting_type]['0.00'][bookmaker]
                    else:
                        continue

                    def get_1x2():
                        try:
                            if isinstance(val, dict):
                                first = val['0']
                                second = val['1']
                                third = val['2']
                            else:
                                first = val[0]
                                second = val[1]
                                third = val[2]
                        except (KeyError, IndexError):
                            return
                        outcome_bet = OutcomeBet.objects.create(
                            first=first,
                            second=second,
                            third=third
                        )
                        if period == 'full_time':
                            outcome_bet.part = OneWayBet.MATCH
                            football_bet.outcome_M = outcome_bet
                        elif period == 'first_half':
                            outcome_bet.part = OneWayBet.FIRST_HALF
                            football_bet.outcome_1hf = outcome_bet
                        else:
                            outcome_bet.part = OneWayBet.SECOND_HALF
                            football_bet.outcome_2hf = outcome_bet
                        outcome_bet.save()

                    def get_odd_even():
                        try:
                            if isinstance(val, dict):
                                first = val['0']
                                second = val['1']
                            else:
                                first = val[0]
                                second = val[1]
                        except (KeyError, IndexError):
                            return
                        odd_even_bet = OddEvenBet.objects.create(
                            first=first,
                            second=second
                        )
                        if period == 'full_time':
                            odd_even_bet.part = OneWayBet.MATCH
                            football_bet.odd_even_M = odd_even_bet
                        elif period == 'first_half':
                            odd_even_bet.part = OneWayBet.FIRST_HALF
                            football_bet.odd_even_1hf = odd_even_bet
                        else:
                            odd_even_bet.part = OneWayBet.SECOND_HALF
                            football_bet.odd_even_2hf = odd_even_bet
                        odd_even_bet.save()

                    def get_dc():
                        try:
                            if isinstance(val, dict):
                                first = val['0']
                                second = val['1']
                                third = val['2']
                            else:
                                first = val[0]
                                second = val[1]
                                third = val[2]
                        except (KeyError, IndexError):
                            return
                        dc_bet = DoubleChanceBet.objects.create(
                            first=first,
                            second=second,
                            third=third
                        )
                        if period == 'full_time':
                            dc_bet.part = OneWayBet.MATCH
                            football_bet.double_chance_M = dc_bet
                        elif period == 'first_half':
                            dc_bet.part = OneWayBet.FIRST_HALF
                            football_bet.double_chance_1hf = dc_bet
                        else:
                            dc_bet.part = OneWayBet.SECOND_HALF
                            football_bet.double_chance_2hf = dc_bet
                        dc_bet.save()

                    def get_dnb():
                        try:
                            if isinstance(val, dict):
                                first = val['0']
                                second = val['1']
                            else:
                                first = val[0]
                                second = val[1]
                        except (KeyError, IndexError):
                            return
                        dnb_bet = DrawNoBetBet.objects.create(
                            first=first,
                            second=second,
                        )
                        if period == 'full_time':
                            dnb_bet.part = OneWayBet.MATCH
                            football_bet.draw_no_bet_M = dnb_bet
                        elif period == 'first_half':
                            dnb_bet.part = OneWayBet.FIRST_HALF
                            football_bet.draw_no_bet_1hf = dnb_bet
                        else:
                            dnb_bet.part = OneWayBet.SECOND_HALF
                            football_bet.draw_no_bet_2hf = dnb_bet
                        dnb_bet.save()

                    def get_bts():
                        try:
                            if isinstance(val, dict):
                                first = val['0']
                                second = val['1']
                            else:
                                first = val[0]
                                second = val[1]
                        except (KeyError, IndexError):
                            return
                        bts_bet = BothTeamToScoreBet.objects.create(
                            first=first,
                            second=second
                        )
                        if period == 'full_time':
                            bts_bet.part = OneWayBet.MATCH
                            football_bet.both_teams_to_score_M = bts_bet
                        elif period == 'first_half':
                            bts_bet.part = OneWayBet.FIRST_HALF
                            football_bet.both_teams_to_score_1hf = bts_bet
                        else:
                            bts_bet.part = OneWayBet.SECOND_HALF
                            football_bet.both_teams_to_score_2hf = bts_bet
                        bts_bet.save()

                    options = {
                        '1x2': get_1x2,
                        'odd/even': get_odd_even,
                        'dc': get_dc,
                        'draw no bet': get_dnb,
                        'both teams to score': get_bts,
                    }
                    options[betting_type]()
                else:
                    # correct_score, htft, euro, asian, over_under
                    if betting_type in result['odds'][period]:
                        odds_types = result['odds'][period][betting_type]
                    else:
                        continue
                    for odd_type in odds_types:
                        if bookmaker in odds_types[odd_type]:
                            val = odds_types[odd_type][bookmaker]
                        else:
                            continue

                        def get_correct_score():
                            goals = odd_type.split(':')
                            correct_score_bet = CorrectScoreBet.objects.create(
                                home=int(goals[0]),
                                away=int(goals[1]),
                                first=val[0]
                            )
                            if period == 'full_time':
                                correct_score_bet.part = OneWayBet.MATCH
                                football_bet.correct_score_M.add(correct_score_bet)
                            elif period == 'first_half':
                                correct_score_bet.part = OneWayBet.FIRST_HALF
                                football_bet.correct_score_1hf.add(correct_score_bet)
                            else:
                                correct_score_bet.part = OneWayBet.SECOND_HALF
                                football_bet.correct_score_2hf.add(correct_score_bet)
                            correct_score_bet.save()

                        def get_htft():
                            htft_bet = HalfTimeFullTimeBet.objects.create(
                                first=val[0],
                                value=odd_type
                            )
                            htft_bet.part = OneWayBet.MATCH
                            football_bet.half_time_full_time_M.add(htft_bet)

                        def get_euro():
                            try:
                                if isinstance(val, dict):
                                    first = val['0']
                                    second = val['1']
                                    third = val['2']
                                else:
                                    first = val[0]
                                    second = val[1]
                                    third = val[2]
                            except (KeyError, IndexError):
                                return
                            euro_bet = EuroHandicapBet.objects.create(
                                first=first,
                                second=second,
                                third=third,
                                value=odd_type
                            )
                            if period == 'full_time':
                                euro_bet.part = OneWayBet.MATCH
                                football_bet.euro_handicap_M.add(euro_bet)
                            elif period == 'first_half':
                                euro_bet.part = OneWayBet.FIRST_HALF
                                football_bet.euro_handicap_1hf.add(euro_bet)
                            else:
                                euro_bet.part = OneWayBet.SECOND_HALF
                                football_bet.euro_handicap_2hf.add(euro_bet)
                            euro_bet.save()

                        def get_asian():
                            try:
                                if isinstance(val, dict):
                                    first = val['0']
                                    second = val['1']
                                else:
                                    first = val[0]
                                    second = val[1]
                            except (KeyError, IndexError):
                                return
                            asian_bet = AsianHandicapBet.objects.create(
                                first=first,
                                second=second,
                                value=odd_type
                            )
                            if period == 'full_time':
                                asian_bet.part = OneWayBet.MATCH
                                football_bet.asian_handicap_M.add(asian_bet)
                            elif period == 'first_half':
                                asian_bet.part = OneWayBet.FIRST_HALF
                                football_bet.asian_handicap_1hf.add(asian_bet)
                            else:
                                asian_bet.part = OneWayBet.SECOND_HALF
                                football_bet.asian_handicap_2hf.add(asian_bet)
                            asian_bet.save()

                        def get_over_under():
                            try:
                                if isinstance(val, dict):
                                    first = val['0']
                                    second = val['1']
                                else:
                                    first = val[0]
                                    second = val[1]
                            except (KeyError, IndexError):
                                return
                            over_under_bet = OverUnderBet.objects.create(
                                first=first,
                                second=second,
                                value=odd_type
                            )
                            if period == 'full_time':
                                over_under_bet.part = OneWayBet.MATCH
                                football_bet.over_under_M.add(over_under_bet)
                            elif period == 'first_half':
                                over_under_bet.part = OneWayBet.FIRST_HALF
                                football_bet.over_under_1hf.add(over_under_bet)
                            else:
                                over_under_bet.part = OneWayBet.SECOND_HALF
                                football_bet.over_under_2hf.add(over_under_bet)
                            over_under_bet.save()

                        options = {
                            'over under': get_over_under,
                            'asian': get_asian,
                            'correct score': get_correct_score,
                            'ht/ft': get_htft,
                            'euro handicap': get_euro
                        }
                        options[betting_type]()
        football_bet.save()


if __name__ == "__main__":
    filename = str(sys.argv[1])
    with open(filename) as f:
        lines = f.readlines()
    for line in lines:
        result = json.loads(line)
        parse_json(result)
