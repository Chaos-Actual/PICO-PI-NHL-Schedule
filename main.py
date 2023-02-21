import json
import urequests as requests
import network
import time
import ntptime
import re
import sys
from machine import Pin, SoftSPI
import st7789 as st7789
import vga1_16x16 as font
"""
    TODO:
        Add functions to call single series overview (all the games of a single series) using the NHL record API. 
        https://records.nhl.com/site/api/playoff-series?cayenneExp=playoffSeriesLetter="A" and seasonId=20182019
"""
BASE_URL = 'http://statsapi.web.nhl.com'
BASE_API = "http://statsapi.web.nhl.com/api/v1/"
GAME_URL = BASE_API + 'game/{0}/linescore'
SCHEDULE_URL = BASE_API + 'schedule?date={0}-{1}-{2}&expand=schedule.linescore'
TEAM_SCHEDULE = BASE_API + 'schedule?teamId={0}&startDate={1}&endDate={2}'
#TEAM_URL = '{0}teams?expand=team.roster,team.stats,team.schedule.previous,team.schedule.next'.format(BASE_API)
#PLAYER_URL = '{0}people/{1}'
OVERVIEW_URL = BASE_API + 'game/{0}/feed/live?site=en_nhl'
#STATUS_URL = BASE_API + 'gameStatus'
# CURRENT_SEASON_URL = BASE_API + 'seasons/current'
# STANDINGS_URL = BASE_API + 'standings'
# STANDINGS_WILD_CARD = STANDINGS_URL + '/wildCardWithLeaders'
# PLAYOFF_URL = BASE_API + "tournaments/playoffs?expand=round.series,schedule.game.seriesSummary&season={}"
# SERIES_RECORD = "https://records.nhl.com/site/api/playoff-series?cayenneExp=playoffSeriesLetter='{}' and seasonId={}"
REQUEST_TIMEOUT = 5
WILD_TEAM_ID = 30  #30 WILD
GAMES_ON_SCREEN  = 3
SCHDULE_DAYS = 17
UTCOFFSET = -5

def format_time(a):
    regex = re.compile("T")
    b = regex.split(a)
    regex = re.compile(":")
    c = regex.split(b[1])
    hour = int(c[0])
    minute = c[1]
    if hour < 5:
        hour =24 - (5 - hour)
        time = str(hour) + ':' + str(minute)
    else:
        hour = hour - 5
        time = str(hour) + ':' + str(minute)
        if hour < 10:
            time = '0' + time 
    return str(time)

def add_days(year, month , day, days_to_add):
    if year % 4 !=0:
        leapyear = 0
    elif  year % 100 != 0:
        leapyear = 1
    elif year % 400 != 0:
        leapyear = 0
    else:
        leapyear = 1
    
    if (month in (1,3,5,7,8,10,12) and day + days_to_add > 31):
        if month == 12:
            year += 1
            month = 1
        day = day - 31 + days_to_add
        month += 1
    elif (month in (4,6,9,11) and day + days_to_add > 30):
        day = day - 30 + days_to_add
        month += 1
    elif (month == 2 and day + days_to_add > 28 + leapyear):
        day = day - (28 + leapyear) + days_to_add
        month += 1 
    else:
        day = day + days_to_add
        
    return str(year) + '-' + str(month) + '-' + str(day)

def connect_wifi(screen):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("network","password")
    # Wait for connect success or failure
    max_wait = 20
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        time.sleep(1)

    # Handle connection error
    if wlan.status() != 3:
        screen.text(font,'wifi connection failed %d' % wlan.status(),15,40,st7789.GREEN)
        raise RuntimeError('wifi connection failed %d' % wlan.status())
    else:
        screen.text(font,'Connected',15,56,st7789.GREEN)
        status = wlan.ifconfig()
        screen.text(font,'IP = ' + status[0]  ,15,72,st7789.GREEN)
    
def print_live_game(screen, game_pk, home, away):
    while 1:
        screen.fill(st7789.BLACK)
        data = requests.get(GAME_URL.format(game_pk), timeout=REQUEST_TIMEOUT)   
        game = data.json()
        time_remaining = ''
        x_cor = 15
        y_cor = 40
        text = away +': ' + str(game['teams']['away']['goals'] )
        screen.text(font,text,x_cor,y_cor,st7789.GREEN)
        y_cor += 16
        text = home +': ' + str(game['teams']['home']['goals'])
        sec = 300
        screen.text(font,text,x_cor,y_cor,st7789.GREEN)
        if game['intermissionInfo']['inIntermission'] == True:
            time_remaining = game['currentPeriodOrdinal'] + ' intermission'
            if game['intermissionInfo']['intermissionTimeRemaining'] > 300:
                sec = game['intermissionInfo']['intermissionTimeRemaining']
        else:
            if game['currentPeriodOrdinal'] =='OT':
                time_remaining = game['currentPeriodTimeRemaining'] + '-' + game['currentPeriodOrdinal']
                if game['currentPeriodTimeRemaining'] =='Final':
                    break
            elif game['currentPeriodTimeRemaining'] == 'Final':
                time_remaining = game['currentPeriodTimeRemaining']
                screen.text(font,time_remaining,x_cor,y_cor,st7789.GREEN)
                break
            else:
                time_remaining = game['currentPeriodOrdinal'] + ' Period '  + game['currentPeriodTimeRemaining']
        y_cor += 16
        screen.text(font,time_remaining,x_cor,y_cor,st7789.GREEN)
        time.sleep(sec)
    
def print_schedule(screen, games):
    x_cor = 15
    y_cor = 40
    text = ''
    now =  get_localtime()
    sec = ((24- now[3]) * 60 *60) - (now[4] *60) - now[5]
    for idx, game in enumerate(games):
        if game['status_code'] in ('3', '4'):#Live
            print_live_game(screen, game['game_pk'], game['home_team_name'], game['away_team_name'])
            y_cor += 64
            return 1
        elif game['status_code'] in ('5', '6', '7'):#Final
            away = game['away_team_name'] +": "+ str(game['away_score'])
            screen.text(font,away,x_cor,y_cor,st7789.GREEN)
            y_cor += 16
            home = game['home_team_name'] +": " + str(game['home_score'])
            screen.text(font,home,x_cor,y_cor,st7789.GREEN)
            y_cor += 16
            screen.text(font,'Final',x_cor,y_cor,st7789.GREEN)
            y_cor += 32
        else: #1,2,8,9 Preview
            text = game['away_team_name'] +" @ "+ game['home_team_name']
            if len(text) > 19:
                text = game['away_team_name'] +" @ "
                screen.text(font,text,x_cor,y_cor,st7789.GREEN)
                y_cor += 16
                text = game['home_team_name']
                screen.text(font,text,x_cor,y_cor,st7789.GREEN)
                y_cor += 16
                text = game['game_date'] + ' @ ' + game['game_time']
                screen.text(font,text,x_cor,y_cor,st7789.GREEN)
                y_cor += 32
            else:
                screen.text(font,text,x_cor,y_cor,st7789.GREEN)
                y_cor += 16
                text = game['game_date'] + ' @ ' + game['game_time']
                screen.text(font,text,x_cor,y_cor,st7789.GREEN)
                y_cor += 32
            if idx == 0:
                now = get_localtime()
                regex = re.compile(":")
                c = regex.split(game['game_time'])
                regex = re.compile('-')
                d = regex.split(game['game_date'])
                if (int(now[2]) == int(d[2])):
                    sec = ((int(c[0])- now[3]) * 60 *60) - (now[4] *60) + (int(c[1]) *60) - now[5]
                if sec <=0:
                    sec = 300
    return sec

def get_team_schedule(team_id):
    num_games = 0
    regex = re.compile(" ")
    now = get_localtime()
    output =[]
    game_info ={}    
    start_date = str(now[0]) + '-' + str(now[1]) + '-' + str(now[2])
    end_date = add_days(now[0], now[1], now[2], SCHDULE_DAYS)
    data = requests.get(TEAM_SCHEDULE.format(team_id, start_date, end_date), timeout=REQUEST_TIMEOUT)
    parsed = data.json()
    if parsed['dates']:
        for games in parsed['dates']:
            for game in games['games']:
                if int(game['teams']['home']['team']['id']) != team_id and int(game['teams']['away']['team']['id']) != team_id:
                    continue;
                game_pk = game['gamePk']
                game_date = format_time(game['gameDate'])
                game_time = games['date']
                status_code = game['status']['statusCode']
                home_score = game['teams']['home']['score']
                away_score = game['teams']['away']['score']
                
                home_team_id = int(game['teams']['home']['team']['id'])
                home_team_name = regex.split(game['teams']['home']['team']['name'])
                if home_team_id in ( 29, 10, 54):
                    home_team_name = home_team_name[len(home_team_name)-2] + ' ' + home_team_name[len(home_team_name)-1]
                else:
                    home_team_name = home_team_name[len(home_team_name)-1]
                
                away_team_id = int(game['teams']['away']['team']['id'])
                away_team_name = regex.split(game['teams']['away']['team']['name'])
                if away_team_id in ( 29, 10, 54):
                    away_team_name = away_team_name[len(away_team_name)-2] + ' ' + away_team_name[len(away_team_name)-1]
                else:
                    away_team_name = away_team_name[len(away_team_name)-1]

                game_info = {
                    'game_pk': game_pk,
                    'game_date': game_time,
                    'game_time': game_date,
                    'home_team_id': home_team_id,
                    'home_team_name': home_team_name,
                    'away_team_id': away_team_id,
                    'away_team_name': away_team_name,
                    'home_score': home_score,
                    'away_score': away_score,
                    'status_code': status_code
                }
                output.append(game_info)
            num_games +=1
            if num_games == GAMES_ON_SCREEN:
                    break    
    return output

def get_localtime():
    now = time.localtime()
    if now[3] < 5:
        return (now[0],now[1], now[2] -1, 24 + now[3] + UTCOFFSET, now[4], now[5],  now[6], now[7]) 
    return (now[0],now[1], now[2], now[3] + UTCOFFSET, now[4], now[5],  now[6], now[7])

def main():
    screen = st7789.ST7789(
            SoftSPI(baudrate=30000000, polarity=1,
                    sck=Pin(10), mosi=Pin(11), miso=Pin(16)),
            240,
            320,
            reset=Pin(12, Pin.OUT),
            cs=Pin(9, Pin.OUT),
            dc=Pin(8, Pin.OUT),
            backlight=Pin(13, Pin.OUT),
            rotation=1)
    connect_wifi(screen)
    led = Pin("LED", Pin.OUT)
    led.on()
    while 1:
        try:
            ntptime.settime()
            break
        except:
            continue
    led.off()  
    now = get_localtime()
    start_date = str(now[0]) + '-' + str(now[1]) + '-' + str(now[2]) + ' ' +  str(now[3]) + ':' +  str(now[4])
    screen.text(font,start_date,15,40,st7789.GREEN)
    led.off()
    time.sleep(5)
    while 1:
        screen.fill(st7789.BLACK)
        games = get_team_schedule(WILD_TEAM_ID)
        sec = print_schedule(screen, games)
        print(sec)
        time.sleep(sec)
        
if __name__ == "__main__":
    main()     

