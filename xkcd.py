import random
from pathlib import Path
from urllib.parse import urlsplit

import requests


REQUEST_TIMEOUT = 30
XKCD_URL = 'https://xkcd.com'


def fetch_comic(session, number=None):
    path = f'/{number}/info.0.json' if number else '/info.0.json'
    response = session.get(XKCD_URL + path, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def fetch_random_comic(session):
    latest_comic = fetch_comic(session)
    latest_number = latest_comic['num']
    # Comic 404 intentionally does not exist on xkcd.
    if latest_number < 404:
        number = random.randint(1, latest_number)
    else:
        number = random.randint(1, latest_number - 1)
        if number >= 404:
            number += 1
    return fetch_comic(session, number)


def download_comic(session, comic, directory):
    image_url = comic['img']
    suffix = Path(urlsplit(image_url).path).suffix or '.png'
    image_path = Path(directory) / f"xkcd-{comic['num']}{suffix}"
    with session.get(
        image_url, stream=True, timeout=REQUEST_TIMEOUT,
    ) as response:
        response.raise_for_status()
        with image_path.open('wb') as image:
            for chunk in response.iter_content(chunk_size=65536):
                image.write(chunk)
    return image_path


def format_comic_header(comic):
    return f"{comic['title']}\n{XKCD_URL}/{comic['num']}/"
