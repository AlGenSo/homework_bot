import logging
import sys
import os
import time
import requests

from telegram import Bot
from logging import StreamHandler
from dotenv import load_dotenv

from exceptions import BotException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN', '1')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '123:X')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

'''Задаём параметры логирования'''
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
    '''Отправление сообщений в телегу.'''
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение {message} в Телегу отправлено.')
    except Exception as ex:
        logger.error(f'Ошибка при отправке сообщения: {ex}')


def get_api_answer(current_timestamp):
    '''Запрос к эндпоинту API-сервиса Я.П.'''
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        homework_statuses = requests.get(
            ENDPOINT,
            HEADERS,
            params,
        )
    except requests.exceptions.RequestException as ex:
        logger.error(f'При запросе произошла ошибка: {ex}')
        raise BaseException(
            f'При запросе произошла ошибка: {ex}'
        )
    logger.info('Ответ от эндпоинта получен')
    return homework_statuses.json()


def check_response(response):
    '''Проверка ответа API на корректность.'''
    if response['homeworks'] is None:
        logger.error('Список заданий не обнаружен')
        raise BotException('Список заданий не обнаружен')

    if response['homeworks'] == []:
        logger.info('Получен пустой список работ')
        return {}

    if response['homeworks'][0].get('status') not in HOMEWORK_STATUSES:
        logger.error('Недокуентированный статус')
        raise BotException('Недокуентированный статус')

    return response['homeworks'][0]


def parse_status(homework):
    '''
    Извлекаем из информации о конкретной домашней работе
    статус этой работы.
    '''
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Обнаружен неизвестный статус!')
        raise BotException(f'Обнаружен неизвестный статус: {homework_status}')

    verdict = HOMEWORK_STATUSES[homework_status]

    logger.info(f'Получен новый статус проверки: {verdict}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    '''Проверка доступности переменных окружения.'''
    if (PRACTICUM_TOKEN is None
       or TELEGRAM_TOKEN is None
       or TELEGRAM_CHAT_ID is None):
        logger.critical('Проблема с переменными окружения')
        return False

    else:
        logger.info('Переменные окружения проверены')
        return True


def main():
    """Основная логика работы бота."""
    if check_tokens():
        logger.onfo('Пременные окружения ОК')
    else:
        logger.critical('Проверте корректность переменных окружения!')
        exit()

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks != [] and homeworks is not None:
                send_message(bot, parse_status(homeworks[0]))
                logger.info('Статус работы получен и отправлен')
            else:
                logger.info('Изменения не обнаружены')
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
