import spotipy
from spotipy.oauth2 import SpotifyOAuth
import credentials
from dataclasses import dataclass

def get_image_as_base64(url):
    '''Convert image straight from URL to base64 without saving as a file'''
    import base64
    import requests
    return base64.b64encode(requests.get(url).content)

def get_all(func):
    '''Decorate a Spotipy function to return all items in a container instead of the limited number offered by the Spotify API calls.'''
    def wrapper(**kwargs):

        temp = func(**kwargs) # use first result to get limit and offset values
        limit = kwargs.pop('limit') if 'limit' in kwargs else temp['limit'] # max number of results that can be returned
        offset = kwargs.pop('offset') if 'offset' in kwargs else temp['offset'] # index of first result to return
        
        items = temp['items'] # tracks|playlists|albums|etc.
        all_items = items # first group of items
        
        while not (len(items) < limit):

            offset += limit # increase offset to get next group of items
            
            items = func(offset=offset, **kwargs)['items'] # next group of results
            all_items += items

        return all_items

    return wrapper

@dataclass(frozen=True)
class PlaylistID: 
    id: str

@dataclass(frozen=True)
class TrackID: 
    id: str

def initialize_playlist(user: str, name: str, description: str, image: bytes) -> PlaylistID:
    pass

def main():
    
    # 'playlist-modify-private' needed to access user's data for the first time
    scope = 'playlist-modify-public, playlist-modify-private, user-top-read, ugc-image-upload'

    ### Authenticate to access account ###

    # Create a Spotipy object with OAuth2 authentication
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            redirect_uri=credentials.redirect_uri,
            scope=scope,  # Specify the required permissions
        )
    )

    if sp.current_user():
        print("You are already logged in.")
    else:
        print("Please follow the instructions to log in:")
        auth_url = sp.auth_manager.get_authorize_url()
        print(f"1. Visit this URL in your browser: {auth_url}")
        print("2. Log in to your Spotify account.")
        print("3. After logging in, you will be redirected to a webpage with a URL.")
        print("4. Copy and paste the entire URL here:")
        authorization_response = input("Enter the URL: ")

        # Exchange the authorization code for an access token
        sp.auth_manager.get_access_token(authorization_response)
        print("You are now logged in!")

    username = sp.current_user()['id']

    ### Create playlist (if needed) ###

    playlist_name = 'On Repeat Forever'#'On Repeat Forever' # new playlist
    playlist_description = 'Any song that has ever shown up in your Top Tracks.' # desc of new playlist

    all_user_playlists = get_all(sp.user_playlists) # decorate Spotipy function so it returns all playlists, not just limit=50
    user_playlists = all_user_playlists(user=username, limit=50)
    user_playlists_names = [playlist['name'] for playlist in user_playlists]

    all_current_user_top_tracks = get_all(sp.current_user_top_tracks)

    playlist_id = ''

    if playlist_name not in user_playlists_names:

        # get playlist cover art
        image_url = 'https://m.media-amazon.com/images/I/61QIdzXGuxL._SL1500_.jpg' # spotify-looking infinity symbol
        playlist_cover = get_image_as_base64(image_url)

        # Create playlist for user
        print(f'Checking client ID and client secret match user "{username}"...')
        sp.user_playlist_create(
            # public by default
            user=username, 
            name=playlist_name,
            description=playlist_description
        )

        # re-retrieve user playlists now that new playlist has been added
        user_playlists = all_user_playlists(user=username, limit=50)
        # get playlist id so you can look up the playlist
        playlist_id, = [playlist['id'] for playlist in user_playlists if playlist['name']==playlist_name]

        # upload playlist cover art
        sp.playlist_upload_cover_image(playlist_id=playlist_id, image_b64=playlist_cover)

        # Alert that playlist has been created
        print(f'Created Spotify playlist "{playlist_name}".')

        # get all user's (long term) top tracks
        long_term_top_tracks = all_current_user_top_tracks(limit=20, offset=0, time_range='long_term')
        long_term_tracks_ids = [track['id'] for track in long_term_top_tracks]

        # add user's long-term top tracks
        if long_term_tracks_ids:
            sp.user_playlist_add_tracks(user=username, playlist_id=playlist_id, tracks=long_term_tracks_ids, position=0)

        # Alert user of added tracks
        if long_term_tracks_ids:
            print('Adding long-term top tracks:')
            for i, track_id in enumerate(long_term_tracks_ids):
                # find track with corresponding id
                for track in long_term_top_tracks:
                    if track['id']==track_id:
                        print(i+1, '-', track['name'], 'on', track['album']['name'], 'by', ', '.join([artist['name'] for artist in track['artists']]))
                        break
        
        print(f'Added {len(long_term_tracks_ids)} long-term tracks to "{playlist_name}" playlist.')
    
    else:
        # get playlist id so you can look up the playlist
        playlist_id, = [playlist['id'] for playlist in user_playlists if playlist['name']==playlist_name]
    
    ### Compare playlist with top-tracks list ###

    # get all user's (medium term) top tracks
    top_tracks = all_current_user_top_tracks(limit=20, offset=0, time_range='medium_term')
    top_tracks_ids = [track['id'] for track in top_tracks]
    
    # get all tracks currently on playlist
    all_user_playlist_tracks = get_all(sp.user_playlist_tracks)
    playlist_tracks = all_user_playlist_tracks(user=username, playlist_id=playlist_id, limit=100)
    # In playlists, Spotify saves date_added, etc., and other info, but we just want the track itself
    playlist_tracks_ids = [track['track']['id'] for track in playlist_tracks]

    # see which top tracks are not on playlist yet
    tracks_to_add = set(top_tracks_ids) - set(playlist_tracks_ids)
    tracks_to_add = list(tracks_to_add) # list of track ids to add (has to be a list for sp.user_playlist_add_tracks)

    ### Add tracks to playlist ###
    
    if tracks_to_add:
        sp.user_playlist_add_tracks(user=username, playlist_id=playlist_id, tracks=tracks_to_add, position=0)

    ### Check which songs were added to the playlist ###

    # Re-retrieve playlist tracks
    playlist_tracks = all_user_playlist_tracks(user=username, playlist_id=playlist_id, limit=100)
    playlist_tracks_ids = [track['track']['id'] for track in playlist_tracks]

    unadded_tracks = set(tracks_to_add) - set(playlist_tracks_ids)
    added_tracks =   set(tracks_to_add) - set(unadded_tracks)

    # Alert user of added tracks
    if added_tracks:
        print('Adding medium-term tracks:')
        for i, track_id in enumerate(added_tracks):
            # find track with corresponding id
            for track in top_tracks:
                if track['id']==track_id:
                    print(i+1, '-', track['name'], 'on', track['album']['name'], 'by', ', '.join([artist['name'] for artist in track['artists']]))
                    break
        
        print(f'Added {len(tracks_to_add)} medium-term tracks to "{playlist_name}" playlist.')

    # Alert user of unadded tracks (just in case some error occured)
    if unadded_tracks:
        print('Failed to add medium-term tracks:')
        for i, track_id in enumerate(unadded_tracks):
            # find track with corresponding id
            for track in top_tracks:
                if track['id']==track_id:
                    print(i+1, '-', track['name'], 'on', track['album']['name'], 'by', ', '.join([artist['name'] for artist in track['artists']]))
                    break
    
    # If nothing prints, nothing happened

if __name__ == '__main__':
    main()
