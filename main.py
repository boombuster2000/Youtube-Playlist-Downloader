import os
import json
import requests
from urllib.parse import urlparse, parse_qs

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')


def load_api_key():
    PLACEHOLDER_KEY = 'YOUR_YOUTUBE_API_KEY'
    if not os.path.exists(CONFIG_FILE):
        default_config = {"apiKey": PLACEHOLDER_KEY}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"Created {CONFIG_FILE}. Please edit it and add your YouTube API key.")
        exit(1)

    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    if not config.get('apiKey') or config['apiKey'] == PLACEHOLDER_KEY:
        print(f"Please set your YouTube API key in {CONFIG_FILE}.")
        exit(1)

    return config['apiKey']


def extract_playlist_id_from_url(input_str):
    try:
        parsed = urlparse(input_str)
        if parsed.scheme and parsed.netloc:
            qs = parse_qs(parsed.query)
            playlist_id = qs.get('list', [None])[0]
            if not playlist_id:
                raise ValueError("Missing 'list' parameter in URL.")
            return playlist_id
        return input_str
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")


def fetch_youtube_playlist_items(api_key, playlist_id):
    next_page_token = ''
    video_urls = []

    while True:
        params = {
            'part': 'snippet',
            'playlistId': playlist_id,
            'maxResults': 50,
            'key': api_key,
        }
        if next_page_token:
            params['pageToken'] = next_page_token

        response = requests.get('https://www.googleapis.com/youtube/v3/playlistItems', params=params)
        if response.status_code != 200:
            raise Exception(f"API Error: {response.text}")

        data = response.json()
        items = data.get('items', [])

        for item in items:
            video_id = item.get('snippet', {}).get('resourceId', {}).get('videoId')
            if video_id:
                video_urls.append(f'https://www.youtube.com/watch?v={video_id}')

        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            break

    return video_urls


def main():
    try:
        api_key = load_api_key()
        user_input = input("Enter playlist URL or ID: ")
        playlist_id = extract_playlist_id_from_url(user_input.strip())

        urls = fetch_youtube_playlist_items(api_key, playlist_id)
        print(f"Fetched {len(urls)} videos:")
        for url in urls:
            print(url)
    except Exception as e:
        print("Error:", str(e))


if __name__ == '__main__':
    main()
