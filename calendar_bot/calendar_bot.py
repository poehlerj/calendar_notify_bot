import datetime
import logging
import logging.config
import os

import pytz
import requests
import telegram
import yaml
import gettext
from icalendar import Calendar
from telegram.ext import Updater, CommandHandler
from telegram.error import TelegramError

from private_config import telegram_token
from public_config import cal_url, check_interval, cal_file_name_new, cal_file_name, server_timezone, \
    chat_ids_file_name, server_language

if server_language is not None:
    os.environ['LANGUAGE'] = server_language
localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locales')
translate = gettext.translation('messages', localedir, fallback=True)
_ = translate.gettext


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
        out = _('*Appointment*\n')
        out = out + '\t_{text}_: {summary}\n'.format(text=_('Eventsummary'), summary=self.summary)
        if str_not_empty(self.description):
            out = out + '\t_{text}_: {description}\n'.format(text=_('Description'), description=self.description)

        out = out + '\t_{text}_: '.format(text=_('Begin'))
        if isinstance(self.time_start, datetime.datetime):
            out += self.time_start.strftime('%H:%M ' + _("on") + ' %d. %m. %Y\n')
        else:
            out += self.time_start.strftime('%d. %m. %Y\n')

        out = out + '\t_{text}_: '.format(text=_('End'))
        if isinstance(self.time_end, datetime.datetime):
            out += self.time_end.strftime('%H:%M ' + _("on") + ' %d. %m. %Y\n')
        else:
            out += self.time_end.strftime('%d. %m. %Y\n')

        if str_not_empty(self.location):
            out = out + '\t_{text}_: {location}\n'.format(text=_('Location'), location=self.location)
        return out + '\n'


def create_event_list(file_name):
    event_list = []
    if not os.path.exists(file_name):
        return None
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
    try:
        bot.send_message(chat_id=chat_id,
                         text=message,
                         parse_mode=telegram.ParseMode.MARKDOWN)
    except TelegramError as error:
        logger.error("Was unable to send message to chatid %d. %s", chat_id, error)


def print_events_to_bot_diff(bot, chat_id, silent=True, return_all=False):
    if os.stat(cal_file_name_new).st_mtime > check_interval:
        r = requests.get(cal_url, allow_redirects=True)
        with open(cal_file_name_new, 'wb+') as file:
            file.write(r.content)

    current_events = create_event_list(cal_file_name_new)
    old_events = create_event_list(cal_file_name)

    new_events = []

    for event in current_events:
        if old_events is not None:
            summary_list = map(lambda x: x.summary, old_events)
        else:
            summary_list = []
        if event.summary not in summary_list or return_all:
            if isinstance(event.time_start, datetime.datetime):
                if event.time_start > datetime.datetime.now(pytz.timezone(server_timezone)):
                    new_events.append(event)
            else:
                if event.time_start > datetime.date.today():
                    new_events.append(event)

    new_events = sorted(new_events, key=lambda x: datetime.datetime.combine(x.time_start, datetime.datetime.min.time()))

    if len(new_events) != 0:
        logger.debug("Got new event(s): " + "\n\t".join(map(lambda x: x.summary, new_events)))
        message = ''
        if not return_all:
            message += '''*{message}:*\n\n'''.format(message=_('I have got new events for you'))
        for event in new_events:
            message += event.to_string()

        send_message(bot, chat_id, message)
    elif not silent:
        send_message(bot, chat_id, _('No new events available'))


def remind(bot, chat_id):
    event_list = create_event_list(cal_file_name)
    remind_list = []
    now = datetime.datetime.now(pytz.timezone(server_timezone))
    for event in event_list:
        start_time = event.time_start
        if isinstance(start_time, datetime.date):
            start_time = datetime.datetime.combine(start_time, datetime.datetime.min.time())
            start_time = start_time.replace(tzinfo=pytz.timezone(server_timezone))
        if start_time < now:
            pass

        seconds_left = (start_time - now).total_seconds()
        if 120 * 60 + check_interval / 2 > seconds_left > 120 * 60 - check_interval / 2:
            remind_list.append(event)
    len_remind_list = len(remind_list)
    if len_remind_list is not 0:
        message = ''
        if len_remind_list == 1:
            message += '''*{message}*\n\n'''.format(message=_('Attention! The following event is coming up'))
        elif len_remind_list > 1:
            message += '''*{message}*\n\n'''.format(message=_('Attention! The following events are coming up'))
        for event in remind_list:
            message += event.to_string()
        send_message(bot, chat_id, message)


def overwrite_ics_file():
    with open(cal_file_name_new, 'r') as new_events_file:
        with open(cal_file_name, 'w+') as current_events_file:
            current_events_file.writelines(new_events_file)


def events(bot, update):
    print_events_to_bot_diff(bot, update.message.chat_id, silent=False, return_all=True)


def callback_interval(bot, job):
    chat_ids_file = open(chat_ids_file_name, 'r')
    lines = [str(line).replace('\n', '') for line in chat_ids_file]
    chat_ids_file.close()
    for line in lines:
        print_events_to_bot_diff(bot, int(line))
        remind(bot, int(line))
    overwrite_ics_file()


def abo(bot, update, remove=False):
    with open(chat_ids_file_name, 'r') as file:
        lines = [str(line).replace('\n', '') for line in file]
    chat_id = str(update.effective_chat.id)
    if chat_id in lines and not remove:
        logger.debug("%s, %s tried to do an abo, but was already receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id, _('You were already subscribed to the event notification system'))
    elif chat_id not in lines and remove:
        logger.debug("%s, %s tried to do a deabo, but was not receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id, _('''You weren't subscribed to the event notification system'''))
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
                         _('You will not get notified, when a new event has been added, anymore'))
        else:
            send_message(bot, update.message.chat_id,
                         _('You wil get notified, when a new event has been added.'))


def de_abo(bot, update):
    abo(bot, update, True)


def print_help(bot, update):
    help_message = _('You can state the following commands:\n') \
                   + _('\t*{appointments}* gives you all the upcoming events in a list sorted '
                       'chronologically\n').format(appointments=_('appointments')) \
                   + _('\t*{sub}* subscribes yourself to the notification system. I will notify you, when a new event '
                       'has been added and when an event is due\n').format(sub=_('sub')) \
                   + _('\t*{unsub}* unsubscribes you from the notification system\n').format(unsub=_('unsub')) \
                   + _('\t*{help}* prints this helping text\n').format(help=_('help'))
    send_message(bot, update.message.chat_id, help_message)
    pass


def main():
    updater = Updater(telegram_token)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler(_('appointments'), events))
    dp.add_handler(CommandHandler(_('sub'), abo))
    dp.add_handler(CommandHandler(_('unsub'), de_abo))
    dp.add_handler(CommandHandler(_('help'), print_help))
    dp.add_handler(CommandHandler(_('start'), print_help))

    j = updater.job_queue
    j.run_repeating(callback_interval, interval=check_interval, first=0)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
