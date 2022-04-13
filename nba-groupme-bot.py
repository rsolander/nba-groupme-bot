import requests
import json
import time
from pytz import utc
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

prev_glob = 0

def main():
    print("main started")
    team = "ATL"
    player = 'T. Young'
    sched = BlockingScheduler(timezone=utc)
    curtime_dt = datetime.utcnow().isoformat()

    def checkGame():
        print('Checking games for ',team,player)
        # Get todays's games
        sb_res = requests.get('https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json')
        scoreboard = json.loads(sb_res.text)["scoreboard"]
        # Find player's game, if there is one today
        if len(scoreboard["games"]) == 0:
            print('No games today')
            return
        for game in scoreboard["games"]:
            print(game['homeTeam']['teamTricode'])
            if game['homeTeam']['teamTricode'] == team or game['awayTeam']['teamTricode'] == team:
                # Set game id
                game_id = game["gameId"]
                # Schedule process for gametime
                gametime_dt = datetime.strptime(game["gameTimeUTC"], "%Y-%m-%dT%H:%M:%SZ")
                print('Scheduling pbp', game_id, gametime_dt)
                sched.add_job(lambda: gameloop(game_id), 'cron', hour=gametime_dt.hour, minute=gametime_dt.minute, id="pbp_job")

    def sendGroupmeMsg(actionlist):
        for play in actionlist:
            payload = {
                "bot_id": "ebfae40129dbf09bf4de75e51b",
                "text": "Certified bum " + player + " missed a " + play["actionType"]
            }
            resp = requests.post('https://api.groupme.com/v3/bots/post', json=payload)

    def processActions(actions):
        global prev_glob
        to_send = []
        for play in actions:
            # Check if the game is over
            if play["actionType"] == "game" and play["subType"] == "end":
                print("Game end detected. Action total: ", prev_glob)
                sendGroupmeMsg([{"actionType":"test"}])
                return False;
            if "playerNameI" in play:
                if player in play["playerNameI"]:
                    print('Action: ' + play["actionType"])
                    if (play["isFieldGoal"] and play['shotResult'] == 'Missed'):
                        print('missed shot detected')
                        to_send.append(play)
        if len(to_send) > 0:
            sendGroupmeMsg(to_send)
            print('Sending msgs: ', to_send)
        return True

    def gameloop(game_id):
        global prev_glob
        live = True
        while live:
            live = playbyplay(game_id)
        prev_glob = 0
        print('Game loop over.')
        sched.remove_job('pbp_job')

    def playbyplay(game_id):
        global prev_glob
        prev_length = prev_glob
        print('Running playbyplay', game_id)
        # Get play-by-play feed
        pbp_res = requests.get('https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_' + game_id + '.json')
        # Handle 403 when game isn't ready
        if (pbp_res.status_code == 403):
            time.sleep(3)
            return True
        # Game is valid/started - remove the job
        #sched.remove_job('pbp_job')
        parsed_res = json.loads(pbp_res.text)
        actions = parsed_res['game']['actions']
        cur_length = len(parsed_res['game']['actions'])
        print('Game endpoint available. ',cur_length,prev_length)
        # Only process new actions, if any
        if (cur_length - prev_length > 0):
            new_actions = actions[-(cur_length - prev_length):]
            if processActions(new_actions) == False:
                return False
        #else:
            #print('Game isnt over but no new actions to process.')
        prev_glob = cur_length
        # Wait 3 seconds then go again
        time.sleep(3)
        return True

    # Every day at _, schedule a game stream if needed
    sched.add_job(checkGame, 'cron', hour=1, minute=30, id="checkgame_job")
    cur_time = datetime.utcnow().isoformat()
    print("checkgame job scheduled, current time: " + cur_time)

    sched.start()

if __name__ == "__main__":
    main()
