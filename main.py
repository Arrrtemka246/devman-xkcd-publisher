import argparse
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import requests
from dotenv import load_dotenv

from telegram_api import TelegramAPIError, call_telegram, publish_comic
from xkcd import (
    download_comic,
    fetch_comic,
    fetch_random_comic,
    format_comic_header,
)


BASE_DIR = Path(__file__).resolve().parent


def positive_comic_number(value):
    number = int(value)
    if number < 1 or number == 404:
        raise argparse.ArgumentTypeError(
            'Укажите положительный номер, кроме отсутствующего комикса 404.',
        )
    return number


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Публикация случайного комикса xkcd в Telegram.',
    )
    parser.add_argument('--comic', type=positive_comic_number)
    parser.add_argument('--env-file', type=Path, default=BASE_DIR / '.env')
    parser.add_argument('--download-only', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=BASE_DIR / 'comics')
    parser.add_argument(
        '--check', action='store_true',
        help='Проверить бота и канал без публикации.',
    )
    return parser.parse_args()


def make_telegram_session(proxy_url=None):
    session = requests.Session()
    if proxy_url:
        session.proxies.update({'http': proxy_url, 'https': proxy_url})
    return session


def run(args):
    load_dotenv(args.env_file)
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not args.download_only and not (token and chat_id):
        raise ValueError(
            'Задайте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env. '
            'Для скачивания без публикации используйте --download-only.',
        )

    if args.check:
        with make_telegram_session(os.getenv('PROXY_URL')) as session:
            bot = call_telegram(session, token, 'getMe')
            chat = call_telegram(
                session, token, 'getChat', data={'chat_id': chat_id},
            )
            member = call_telegram(
                session, token, 'getChatMember',
                data={'chat_id': chat_id, 'user_id': bot['id']},
            )
            if chat['type'] == 'channel' and not (
                member['status'] == 'creator'
                or member.get('can_post_messages')
            ):
                raise ValueError('У бота нет права публикации в этом канале.')
            print(f"Бот: @{bot['username']}")
            print(f"Канал: {chat.get('title', chat['id'])}")
            print('Доступ проверен. Публикаций не было.')
        return

    with requests.Session() as session:
        comic = (
            fetch_comic(session, args.comic) if args.comic
            else fetch_random_comic(session)
        )
        print(format_comic_header(comic))
        print(comic['alt'])
        if args.download_only:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            image_path = download_comic(session, comic, args.output_dir)
            print(f'Сохранено: {image_path}')
            return

        with TemporaryDirectory(prefix='xkcd-') as directory:
            image_path = download_comic(session, comic, directory)
            with make_telegram_session(os.getenv('PROXY_URL')) as telegram:
                message = publish_comic(
                    telegram, token, chat_id, image_path, comic,
                )
            print(f"Опубликовано. Номер сообщения: {message['message_id']}")
        print('Временный файл удалён.')


def main():
    args = parse_arguments()
    if args.check and args.download_only:
        print('--check и --download-only несовместимы.', file=sys.stderr)
        return 2
    try:
        run(args)
    except requests.RequestException as error:
        status = getattr(error.response, 'status_code', None)
        detail = f' (HTTP {status})' if status else ''
        print(f'Ошибка обращения к xkcd{detail}.', file=sys.stderr)
        return 1
    except (TelegramAPIError, ValueError, KeyError, OSError) as error:
        print(f'Ошибка: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
