# remember to export client id, secret and redirect to run in development mode

import os
from flask import Flask, session, request, redirect, render_template, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit
import spotipy
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)
socketio = SocketIO(app)

gameinprogress = False
users = []
trackinfo = []
userpoints = {}
userplaylists = {}
roundselection = []
roundnumber = 1
playedusers = []

@app.route('/')
def index():
    global users
    global userpoints
    global userplaylists
    global gameinprogress
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope='playlist-read-private playlist-read-collaborative', cache_handler=cache_handler, show_dialog=True)

    if request.args.get("code"):
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')

    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        auth_url = auth_manager.get_authorize_url()
        return f'<h2><a href="{auth_url}">Sign in</a></h2>'

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    if spotify.me()["display_name"] not in users:
        users.append(spotify.me()["display_name"])
        userplaylists[spotify.me()["display_name"]] = spotify.current_user_playlists()
        userpoints[spotify.me()["display_name"]] = 0
        socketio.emit('refresh_page')
        
    if gameinprogress:
        return render_template('gameinprogress.html', name = spotify.me()["display_name"])
    else:
        return render_template('gamestart.html', userpoints = userpoints, name = spotify.me()["display_name"])


@app.route('/sign_out')
def sign_out():
    session.pop("token_info", None)
    return redirect('/')

@app.route('/game_screen')
def game_screen():
    info = trackinfo[roundnumber]
    return render_template('game_screen.html', userpoints = userpoints, roundnumber = roundnumber, playlist_name=info[0], tracks_info=info[1], users = users)


@app.route('/calculatepoints', methods=['POST'])
def calculatepoints():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)

    chosenuser = request.form.get("user")
    if chosenuser == roundselection[roundnumber]:
        userpoints[spotify.me()["display_name"]] += 1

    return redirect('/waitingscreen')

@app.route('/waitingscreen')
def waitingscreen():
    global roundnumber 
    global playedusers
    playedusers.append("me")
    if len(playedusers) == len(users):
        roundnumber += 1
        socketio.emit('ready_to_play', {'location': url_for('game_screen')})
        playedusers = []
        return redirect('/game_screen')
    return render_template('waitingscreen.html')

@app.route('/gameinitialize', methods=['POST'])
def gameinitialize():
    global gameinprogress
    global roundselection
    global roundnumber
    global trackinfo
    global playedusers
    gameinprogress = True

    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)

    for i in range(11):
        random_user = random.choice(users)
        roundselection.append(random_user)
        user_playlists = userplaylists[random_user]
        user_playlist = random.choice(user_playlists['items'])
        all_playlist_tracks = spotify.playlist_tracks(user_playlist['id'])
        user_playlist_tracks = random.sample(all_playlist_tracks['items'], min(5, len(all_playlist_tracks['items'])))
        user_playlist_tracks_info = []
        for track in user_playlist_tracks:
            track_info = {
                'name': track['track']['name'],
                'artist': ', '.join(artist['name'] for artist in track['track']['artists']),
                'album': track['track']['album']['name'],
            }
            user_playlist_tracks_info.append(track_info)
        trackinfo.append((user_playlist['name'], user_playlist_tracks_info))
    
    socketio.emit('start_game', {'location': url_for('game_screen')})

    return redirect('/game_screen')

@app.route('/redirect_all')
def redirect_all():
    socketio.emit('redirect_all_clients', {'redirect_url': '/game_screen'})
    return redirect('/')

@app.route('/final_screen')
def final_screen():
    return render_template('finalscreen.html', userpoints = userpoints)

# if __name__ == '__main__':
#     socketio.run(app, port=int(os.environ.get("PORT", os.environ.get("SPOTIPY_REDIRECT_URI", 8080).split(":")[-1])))

if __name__ == '__main__':
    socketio.run(app)