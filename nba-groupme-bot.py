import requests
import json
import time
from pytz import utc
from datetime import datetime
from PIL import Image
from apscheduler.schedulers.blocking import BlockingScheduler

prev_glob = 0
img_width = 400

def main():
    print("main started")
    team = "PHI"
    player = 'J. Harden'
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

    def updateHardenPic():
        image = Image.open('harden2.jpeg')
        new_image = image.resize((img_width, 400))
        new_image = new_image.crop((img_width/4,0,3*img_width/4,400))
        new_image.save('hardenedit.jpeg')
        data = open('./hardenedit.jpeg', 'rb').read()
        res = requests.post(url='https://image.groupme.com/pictures',
                    data=data,
                    headers={'Content-Type': 'image/jpeg',
                             'X-Access-Token': 'nlFxoVQGqzVqErEiGW3HOCFKgXJeKCqvKeffs7HI'})
        return json.loads(res.content)['payload']['url']

    def sendGroupmeMsg(actionlist):
        global img_width
        for play in actionlist:
            edit_url = updateHardenPic()
            payload = {
                "bot_id": "6d765b3c18fd6547166f92623e",
                "text": "Harden misses a " + play["actionType"] + " shot.",
                "attachments": [
                    {
                        "type": "image",
                        "url": edit_url
                    }
                ]
            }
            resp = requests.post('https://api.groupme.com/v3/bots/post', data=json.dumps(payload))
            img_width = img_width + 200

    def processActions(actions):
        global prev_glob
        to_send = []
        for play in actions:
            # Check if the game is over
            if play["actionType"] == "game" and play["subType"] == "end":
                print("Game end detected. Action total: ", prev_glob)
                return False;
            if "playerNameI" in play:
                if player in play["playerNameI"]:
                    print('Player action: ' + play["actionType"])
                    if (play["isFieldGoal"] and play['shotResult'] == 'Missed'):
                        to_send.append(play)
        if len(to_send) > 0:
            sendGroupmeMsg(to_send)
            print('Sending msgs: ', to_send)
        return True

    def gameloop(game_id):
        global prev_glob, img_width
        live = True
        while live:
            live = playbyplay(game_id)
        prev_glob = 0
        print('Game loop over.')
        sched.remove_job('pbp_job')
        img_width = 400

    def playbyplay(game_id):
        global prev_glob
        prev_length = prev_glob
        # Get play-by-play feed
        pbp_res = requests.get('https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_' + game_id + '.json')
        # Handle 403 when game isn't ready
        if (pbp_res.status_code == 403):
            time.sleep(3)
            return True
        # Game is valid/started
        parsed_res = json.loads(pbp_res.text)
        actions = parsed_res['game']['actions']
        cur_length = len(parsed_res['game']['actions'])
        # Only process new actions, if any
        if (cur_length - prev_length > 0):
            new_actions = actions[-(cur_length - prev_length):]
            if processActions(new_actions) == False:
                return False
        prev_glob = cur_length
        time.sleep(3)
        return True

    # Every day at 17:10 UTC, schedule a game stream if needed
    sched.add_job(checkGame, 'cron', hour=16, minute=50, id="checkgame_job")
    cur_time = datetime.utcnow().isoformat()
    print("checkgame job scheduled, current time: " + cur_time)

    sched.start()

if __name__ == "__main__":
    main()
