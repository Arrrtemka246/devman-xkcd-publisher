import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

import main
from telegram_api import TelegramAPIError, call_telegram, publish_comic
from xkcd import fetch_random_comic


class PublisherTests(unittest.TestCase):
    def test_random_comic_skips_missing_number_404(self):
        session = MagicMock()
        latest = {'num': 1000}
        with patch('xkcd.fetch_comic', side_effect=[latest, {'num': 405}]) as get:
            with patch('xkcd.random.randint', return_value=404):
                self.assertEqual(fetch_random_comic(session)['num'], 405)
        self.assertEqual(get.call_args.args, (session, 405))

    def test_connection_error_does_not_expose_bot_token(self):
        session = MagicMock()
        token = 'private-test-token'
        session.post.side_effect = requests.ConnectionError(
            f'https://api.telegram.org/bot{token}/sendPhoto',
        )
        with self.assertRaises(TelegramAPIError) as caught:
            call_telegram(session, token, 'sendPhoto')
        self.assertNotIn(token, str(caught.exception))

    def test_long_comment_is_published_without_truncation(self):
        comic = {'num': 353, 'title': 'Python', 'alt': 'a' * 5000}
        calls = []

        def record(session, token, method, data=None, files=None):
            calls.append((method, data))
            return {'message_id': 1}

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'comic.png'
            image.write_bytes(b'example')
            with patch('telegram_api.call_telegram', side_effect=record):
                publish_comic(None, 'test', 'channel', image, comic)
        self.assertEqual(calls[0][0], 'sendPhoto')
        self.assertEqual(calls[0][1]['caption'], 'Python\nhttps://xkcd.com/353/')
        self.assertEqual(''.join(call[1]['text'] for call in calls[1:]),
                         comic['alt'])

    def test_temporary_image_is_removed_even_after_publication_failure(self):
        comic = {'num': 353, 'title': 'Python', 'alt': 'Comment'}
        image_paths = []

        def download(session, comic, directory):
            image = Path(directory) / 'comic.png'
            image.write_bytes(b'example')
            image_paths.append(image)
            return image

        args = argparse.Namespace(
            env_file=Path('/nonexistent-test-env'), check=False,
            download_only=False, comic=353,
        )
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test', 'TELEGRAM_CHAT_ID': 'test',
        }):
            with patch('main.fetch_comic', return_value=comic):
                with patch('main.download_comic', side_effect=download):
                    with patch('main.publish_comic',
                               side_effect=TelegramAPIError('failed')):
                        with self.assertRaises(TelegramAPIError):
                            main.run(args)
        self.assertEqual(len(image_paths), 1)
        self.assertFalse(image_paths[0].exists())
        self.assertFalse(image_paths[0].parent.exists())


if __name__ == '__main__':
    unittest.main()
