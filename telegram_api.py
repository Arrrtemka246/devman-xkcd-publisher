import requests

from xkcd import format_comic_header


class TelegramAPIError(Exception):
    pass


def call_telegram(session, token, method, data=None, files=None):
    url = f'https://api.telegram.org/bot{token}/{method}'
    try:
        response = session.post(url, data=data, files=files, timeout=60)
    except requests.RequestException:
        # requests errors can contain the bot token in the request URL.
        raise TelegramAPIError(
            'Не удалось связаться с Telegram. Проверьте сеть или PROXY_URL.',
        ) from None
    try:
        payload = response.json()
    except ValueError:
        raise TelegramAPIError(
            'Telegram вернул некорректный ответ '
            f'(HTTP {response.status_code}).',
        ) from None
    if not response.ok or not payload.get('ok'):
        description = str(payload.get('description', 'Неизвестная ошибка'))
        raise TelegramAPIError(description.replace(token, '[скрыто]'))
    return payload['result']


def publish_comic(session, token, chat_id, image_path, comic):
    header = format_comic_header(comic)
    comment = comic['alt']
    caption = f'{header}\n\n{comment}'
    # Telegram limits photo captions to 1024 characters. Keep long alt texts
    # complete by sending them as separate messages after the photo.
    separate_comment = len(caption) > 1024
    with image_path.open('rb') as image:
        message = call_telegram(
            session, token, 'sendPhoto',
            data={
                'chat_id': chat_id,
                'caption': header if separate_comment else caption,
            },
            files={'photo': image},
        )
    if separate_comment:
        for start in range(0, len(comment), 4096):
            call_telegram(
                session, token, 'sendMessage',
                data={'chat_id': chat_id, 'text': comment[start:start + 4096]},
            )
    return message
