import datetime
import logging
import logging.config
import os

import pytz
import requests
import telegram
import yaml
from icalendar import Calendar
from telegram.ext import Updater, CommandHandler

from private_config import telegram_token
from public_config import cal_url, check_interval, cal_file_name_new, cal_file_name, server_timezone, chat_ids_file_name


def setup_logging(default_path='logging.yaml', default_level=logging.INFO, env_key='LOG_CFG'):
    """
    Setup logging configuration
    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


# Enable logging
setup_logging()
logger = logging.getLogger(__name__)


def str_not_empty(input):
    return input is not None and input != ''


class Event:
    def __init__(self, summary, description, time_start, time_end, location):
        self.summary = summary
        self.description = description
        self.time_start = time_start
        self.time_end = time_end
        self.location = location

    def to_string(self):
        out = '*Termin*\n'
        out = out + '\t__Veranstaltungsbezeichnung__: ' + self.summary + '\n'
        if str_not_empty(self.description):
            out = out + '\t__Beschreibung__: ' + self.description + '\n'

        out = out + '\t__Start__: '
        if isinstance(self.time_start, datetime.datetime):
            out += self.time_start.strftime('%H:%M on %d. %m. %Y\n')
        else:
            out += self.time_start.strftime('%d. %m. %Y\n')

        out = out + '\t__Ende__: '
        if isinstance(self.time_end, datetime.datetime):
            out += self.time_end.strftime('%H:%M on %d. %m. %Y\n')
        else:
            out += self.time_end.strftime('%d. %m. %Y\n')

        if str_not_empty(self.location):
            out = out + '\t__Ort__: ' + self.location + '\n'
        return out + '\n'


def create_event_list(file_name):
    event_list = []
    file = open(file_name, 'rb')
    cal = Calendar.from_ical(file.read())
    for component in cal.walk():
        if component.name == "VEVENT":
            event = Event(component.get('summary'),
                          component.get('description'),
                          component.decoded('dtstart'),
                          component.decoded('dtend'),
                          component.get('location'))
            event_list.append(event)
    file.close()
    return event_list


def send_message(bot, chat_id, message):
    logger.debug("Sending message to chatid %d with message: \n\t%s ", chat_id, message)
    bot.send_message(chat_id=chat_id,
                     text=message,
                     parse_mode=telegram.ParseMode.MARKDOWN)


def print_events_to_bot_diff(bot, chat_id, silent=True, return_all=False):
    if os.stat(cal_file_name_new).st_mtime > check_interval:
        r = requests.get(cal_url, allow_redirects=True)
        with open(cal_file_name_new, 'wb+') as file:
            file.write(r.content)

    current_events = create_event_list(cal_file_name_new)
    old_events = create_event_list(cal_file_name)

    new_events = []

    for event in current_events:
        summary_list = map(lambda x: x.summary, old_events)
        if event.summary not in summary_list or return_all:
            if isinstance(event.time_start, datetime.datetime):
                if event.time_start > datetime.datetime.now(pytz.timezone(server_timezone)):
                    new_events.append(event)
            else:
                if event.time_start > datetime.date.today():
                    new_events.append(event)

    new_events = sorted(new_events, key=lambda x: x.time_start)

    if len(new_events) != 0:
        logger.debug("Got new event(s): " + "\n\t".join(map(lambda x: x.summary, new_events)))
        message = ''
        for event in new_events:
            message += event.to_string()

        send_message(bot, chat_id, message)
    elif not silent:
        send_message(bot, chat_id, 'Keine neuen Events verfügbar')


def overwrite_ics_file():
    with open(cal_file_name_new, 'r') as new_events_file:
        with open(cal_file_name, 'w+') as current_events_file:
            current_events_file.writelines(new_events_file)


def events(bot, update):
    print_events_to_bot_diff(bot, update.message.chat_id, silent=False, return_all=True)


def callback_minute(bot, job):
    chat_ids_file = open(chat_ids_file_name, 'r')
    lines = [str(line).replace('\n', '') for line in chat_ids_file]
    chat_ids_file.close()
    for line in lines:
        print_events_to_bot_diff(bot, int(line))
    overwrite_ics_file()


def abo(bot, update, remove=False):
    with open(chat_ids_file_name, 'r') as file:
        lines = [str(line).replace('\n', '') for line in file]
    chat_id = str(update.effective_chat.id)
    if chat_id in lines and not remove:
        logger.debug("%s, %s tried to do an abo, but was already receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id, 'Du hast die automatische Kalenderbenachrichtigung bereits abonniert')
    elif chat_id not in lines and remove:
        logger.debug("%s, %s tried to do a deabo, but was not receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id,
                     'Du hattest die automatische Kalenderbenachrichtigung nicht abonniert')
    else:
        if remove:
            logger.debug(chat_id + ", " + update.effective_user.username + " did a deabo")
            lines.remove(chat_id)
        else:
            logger.debug(chat_id + ", " + update.effective_user.username + " did a abo")
            lines.append(chat_id)

        with open(chat_ids_file_name, 'w') as chat_file:
            chat_file.write("\n".join(lines))
        if remove:
            send_message(bot, update.message.chat_id,
                         'Du wirst nun nicht mehr benachrichtigt, wenn eine neuer Kalendereintrag hinzukommt')
        else:
            send_message(bot, update.message.chat_id,
                         'Du wirst nun benachrichtigt, wenn neue Kalendereinträge hinzukommen')


def de_abo(bot, update):
    abo(bot, update, True)


def main():
    updater = Updater(telegram_token)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('termine', events))
    dp.add_handler(CommandHandler('abo', abo))
    dp.add_handler(CommandHandler('deabo', de_abo))

    j = updater.job_queue
    j.run_repeating(callback_minute, interval=check_interval, first=0)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
