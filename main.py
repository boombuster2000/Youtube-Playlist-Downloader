import os
import json
import time
import random
from typing import Optional
from urllib.parse import urlparse, parse_qs
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, DownloadColumn, TransferSpeedColumn
import stealth_requests as requests

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    ),
    "Referer": "https://cnvmp3.com/v25",
    "authority": "cnvmpp3.com"
}

console = Console()

def extract_youtube_video_id(url: str) -> Optional[str]:
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

def load_api_key() -> str:
    placeholder_key = 'YOUR_YOUTUBE_API_KEY'
    if not os.path.exists(CONFIG_FILE):
        default_config = {"apiKey": placeholder_key}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"Created {CONFIG_FILE}. Please edit it and add your YouTube API key.")
        exit(1)

    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    if not config.get('apiKey') or config['apiKey'] == placeholder_key:
        print(f"Please set your YouTube API key in {CONFIG_FILE}.")
        exit(1)

    return config['apiKey']

def extract_playlist_id_from_url(input_str: str) -> str:
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

def fetch_youtube_playlist_items(api_key: str, playlist_id: str) -> list[str]:
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

def fetch_video_titles(api_key: str, video_urls: list[str]) -> list[tuple[str, str]]:
    def extract_id(url):
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc and parsed.path == '/watch':
            return parse_qs(parsed.query).get('v', [None])[0]
        elif 'youtu.be' in parsed.netloc:
            return parsed.path.lstrip('/')
        return None

    # Build a mapping from video IDs to URLs; skip URLs with no valid ID.
    id_map = {}
    for url in video_urls:
        video_id = extract_id(url)
        if video_id is not None:
            id_map[video_id] = url

    # Collect only valid video IDs.
    ids = list(id_map.keys())
    titles = []

    # Process in batches of 50.
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        # Join the list of video IDs into a comma-separated string.
        id_string = ",".join(batch)
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet",
                "id": id_string,
                "key": api_key
            }
        )
        if response.status_code != 200:
            raise Exception(f"Failed to fetch video metadata: {response.text}")

        data = response.json()
        for item in data.get("items", []):
            vid = item["id"]
            title = item["snippet"]["title"]
            titles.append((title, id_map[vid]))

    return titles


def get_check_database_response(url: str, video_id: str) -> Optional[dict]:
    params = {
        "formatValue": 1,
        "quality": 0,
        "youtube_id": video_id
    }
    response = requests.post(url, json=params)

    if response.status_code != 200:
        raise Exception(f"Check Database Error: {response.text}")

    time.sleep(random.uniform(2, 5))
    try:
        return response.json()
    except json.JSONDecodeError:
        print("Error: Received non-JSON response:\n", response.text)
        return None

def download_mp3(url: str, filename: Optional[str] = None, folder: str = "downloads") -> None:
    response = requests.get(url, headers=HEADERS, stream=True)

    if response.status_code != 200:
        raise Exception(f"Failed to download MP3. Status: {response.status_code}\n\n{response.text[:300]}")

    if filename is None:
        filename = os.path.basename(url.split("?")[0])

    if not filename.endswith(".mp3"):
        filename += ".mp3"

    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, filename)

    total_size = int(response.headers.get('content-length', 0))
    with open(file_path, "wb") as f, Progress(
        TextColumn("{task.fields[filename]}", justify="right"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("download", filename=filename, total=total_size)
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                progress.update(task, advance=len(chunk))

    console.print(f"✅ Saved: {file_path}", style="green")
    time.sleep(random.uniform(2, 5))

def get_video_data(url: str) -> dict:
    api_url = "https://cnvmp3.com/get_video_data.php"
    response = requests.post(api_url, json={"url": url, "token": "1234"})

    if response.status_code != 200:
        raise Exception(f"Failed to get video data.\n{response.text}")

    time.sleep(random.uniform(2, 5))
    return response.json()

def download_video_ucep(url: str, title: str) -> dict:
    api_url = "https://cnvmp3.com/download_video_ucep.php"
    response = requests.post(api_url, headers=HEADERS, json={
        "url": url,
        "quality": 0,
        "title": title,
        "formatValue": 1
    })

    if response.status_code != 200:
        raise Exception(f"Failed download video ucep.\n{response.text}")

    data = response.json()
    if data.get("success"):
        print("Downloading")
        download_mp3(data["download_link"], title)

    time.sleep(random.uniform(2, 5))
    return data

def insert_to_database(video_url: str, download_url: str, title: str) -> dict:
    api_url = "https://cnvmp3.com/insert_to_database.php"
    video_id = extract_youtube_video_id(video_url)

    response = requests.post(api_url, headers=HEADERS, json={
        "youtube_id": video_id,
        "server_path": download_url,
        "quality": 0,
        "title": title,
        "formatValue": 1
    })

    if response.status_code != 200:
        raise Exception(f"Failed to insert to database.\n{response.text}")

    data = response.json()
    if not data.get("success"):
        raise Exception(f"Failed to insert to database.\n{data['error']}")

    print("Inserted into database")
    time.sleep(random.uniform(2, 5))
    return data

def process_youtube_mp3_download(url: str) -> None:
    check_db_url = "https://cnvmp3.com/check_database.php"
    video_id = extract_youtube_video_id(url)

    if not video_id:
        raise ValueError("Invalid YouTube URL. Could not extract video ID.")

    db_response = get_check_database_response(check_db_url, video_id)

    if not db_response:
        return

    if db_response.get("success"):
        download_url = db_response["data"]["server_path"]
        title = db_response["data"]["title"]
        download_mp3(download_url, title)
    else:
        video_data = get_video_data(url)
        if video_data.get("success"):
            title = video_data["title"]
            ucep_resp = download_video_ucep(url, title)
            insert_to_database(url, ucep_resp["download_link"], title)

def preview_playlist_titles(urls: list[str], api_key: str) -> list[tuple[str, str]]:
    preview_data = fetch_video_titles(api_key, urls)
    table = Table(title="YouTube Playlist Download Queue")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Title", style="bold")
    table.add_column("URL", style="magenta")

    for idx, (title, url) in enumerate(preview_data, start=1):
        table.add_row(str(idx), title, url)

    console.print(table)
    return preview_data

def main() -> None:
    try:
        api_key = load_api_key()
        user_input = input("Enter playlist URL or ID: ").strip()
        playlist_id = extract_playlist_id_from_url(user_input)
        urls = fetch_youtube_playlist_items(api_key, playlist_id)
        playlist = preview_playlist_titles(urls, api_key)

        for index, (title, url) in enumerate(playlist, start=1):
            process_youtube_mp3_download(url)

            if index % 5 == 0:
                print("Cooling down...")
                time.sleep(10)

    except Exception as e:
        raise Exception("Error:", str(e))

if __name__ == '__main__':
    main()