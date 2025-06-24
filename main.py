import os
import json
import stealth_requests as requests
from urllib.parse import urlparse, parse_qs
from typing import Optional

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')


def extract_youtube_video_id(url: str) -> Optional[str]:
    """
    Extracts the video ID from a YouTube URL using urllib.parse.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    """
    parsed = urlparse(url)

    if parsed.hostname in ('youtu.be',):
        return parsed.path.lstrip('/')

    if parsed.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed.path == '/watch':
            query = parse_qs(parsed.query)
            return query.get('v', [None])[0]
        elif parsed.path.startswith('/embed/'):
            return parsed.path.split('/')[2]

    return None

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


def download_mp3(url):
    check_database_url = "https://cnvmp3.com/check_database.php"
    video_id = extract_youtube_video_id(url)

    if not video_id:
        raise ValueError("Invalid YouTube URL. Could not extract video ID.")

    print(video_id)
    params = {
        "formatValue": 1,
        "quality": 0,
        "youtube_id": video_id
    }

    response = requests.post(check_database_url, json=params)

    if response.status_code != 200:
        raise Exception(f"Check Database Error: {response.text}")

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Error: Received non-JSON response:")
        print("Response content:\n", response.text)
        return

    print("Response JSON:\n", data)

    

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
    #main()
    download_mp3("https://www.youtube.com/watch?v=99l4Z0Rwanw")
