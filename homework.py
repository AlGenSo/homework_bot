import json
import logging
import sys
import os
import time
from typing import Dict, List
import requests

from telegram import Bot, TelegramError
from logging import StreamHandler
from dotenv import load_dotenv

from exceptions import BotException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_CONDITION = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(lineno)s'
)
logger = logging.getLogger(__name__)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправление сообщений в телегу."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение {message} в Телегу отправлено.')
    except TelegramError as ex:
        logger.error(f'Ошибка при отправке сообщения: {ex}')
        raise BotException(f'Ошибка при отправке сообщения: {ex}')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса Я.П."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except requests.exceptions.RequestException as ex:
        logger.error(f'При запросе произошла ошибка: {ex}')
        raise BaseException(
            f'При запросе произошла ошибка: {ex}'
        )

    if homework_statuses.status_code != 200:
        raise BotException(
            f'Ошибка доступа ендпойнта, {homework_statuses.status_code}'
        )

    try:
        json_hw_status = homework_statuses.json()
    except json.JSONDecodeError:
        raise BotException('Ошибка преобразования в json.')

    logger.info('Ответ от эндпоинта получен')

    return json_hw_status


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, Dict):
        raise TypeError(
            'response прихлдит не в виде словаря'
        )

    if response.get('homeworks') is None:
        logger.error('Список заданий не обнаружен')
        raise BotException('Список заданий не обнаружен')

    if not isinstance(response['homeworks'], List):
        raise TypeError(
            'Домашки приходят не в виде списка в ответ от API'
        )

    if response.get('current_date') is None:
        logger.error('Значение ключа current_date отсутствует')
        raise BotException('Значение ключа current_date отсутствует')

    return response['homeworks']


def parse_status(homework):
    """Извлекаем из информации о конкретной домашней работе.
    статус этой работы.
    """
    if 'homework_name' not in homework:
        raise KeyError(
            f'Отсутствует ключ "homework_name" : homework = {homework}.'
        )

    if 'status' not in homework:
        raise KeyError(
            f'Отсутствует ключ "status" : homework = {homework}.'
        )

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_CONDITION:
        logger.error('Обнаружен неизвестный статус!')
        raise BotException(
            f'Обнаружен недокументироавнный статус: {homework_status}')

    if homework_name is None:
        BotException(f'Пустое значение названия работы: {homework_name}')

    verdict = HOMEWORK_CONDITION[homework_status]

    logger.info(f'Получен новый статус проверки: {verdict}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    TOKENS = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ]
    for element in TOKENS:
        if element is None:
            logger.critical('Проблема с переменной окружения!')
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Проверте корректность переменных окружения!')
        exit()

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks != [] and homeworks is not None:
                send_message(bot, parse_status(homeworks[0]))
                current_timestamp = response['current_date']
                logger.info('Статус работы получен и отправлен')
                logger.info(
                    'Обновилась переменная current_timestamp:'
                    f'{current_timestamp}'
                )
            else:
                logger.info('Изменения не обнаружены')
                current_timestamp = response['current_date']
                logger.info(
                    'Обновилась переменная current_timestamp:'
                    f'{current_timestamp}'
                )

        except TelegramError as ex:
            logger.error(f'Ошибка при отправке сообщения: {ex}')
            raise BotException(f'Ошибка при отправке сообщения: {ex}')

        except Exception as error:
            new_message = f'Сбой в работе программы: {error}'
            logger.critical(new_message)
            if new_message != message:
                bot.send_message(TELEGRAM_CHAT_ID, new_message)
                logger.info('Новое сообщение отправлено в Телегу')
                message = new_message

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
