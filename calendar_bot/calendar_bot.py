import logging
import logging.config
import os
from datetime import datetime

import pytz
import requests
import telegram
import yaml
from icalendar import Calendar
from jinja2 import Environment, PackageLoader, select_autoescape
from telegram.error import TelegramError
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from private_config import telegram_token
from public_config import cal_url, check_interval, cal_file_name_new, cal_file_name, server_timezone, \
    sub_chat_ids_file_name, remind_chat_ids_file_name, remind_time, version_file

env = Environment(
    loader=PackageLoader('calendar_bot', 'templates'),
    autoescape=select_autoescape(['md']),
)
env.globals.update(
    is_include_time=lambda date_time: date_time.time() == datetime.min.time()
)

event_template = env.get_template('event.md.j2')
help_template = env.get_template('help.md.j2')
sub_unsub_template = env.get_template('sub_unsub.md.j2')
messages_template = env.get_template('messages.md.j2')
reminder_template = env.get_template('reminder.md.j2')
status_template = env.get_template('status.md.j2')
version_template = env.get_template('version_features.md.j2')


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


def str_not_empty(value):
    return value is not None and value != ''


def ensure_datetime(value):
    if not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
        value = value.replace(tzinfo=pytz.timezone(server_timezone))
    return value


class Event:
    def __init__(self, summary, description, time_start, time_end, location):
        self.summary = summary
        self.description = description
        self.time_start = ensure_datetime(time_start)
        self.time_end = ensure_datetime(time_end)
        self.location = location
        if (self.time_end - self.time_start).total_seconds() == 24 * 60 * 60:
            self.all_day = True
        else:
            self.all_day = False

    def to_string(self):
        return event_template.render(
            name=self.summary,
            description=self.description,
            start=self.time_start,
            end=self.time_end,
            location=self.location,
            all_day=self.all_day
        )


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


def print_unknown_command(bot, chat_id, command, args):
    message = messages_template.render(unknown_command=True, command=command, command_args=" ".join(args))
    send_message(bot, chat_id, message)


def get_events_diff(silent=True, return_all=False):
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
            if event.time_start > datetime.now(pytz.timezone(server_timezone)):
                new_events.append(event)

    new_events = sorted(new_events, key=lambda x: datetime.combine(x.time_start, datetime.min.time()))

    if len(new_events) != 0:
        logger.debug("Got new event(s): " + "\n\t".join(map(lambda x: x.summary, new_events)))
        message = ''
        if not return_all:
            message += messages_template.render(new_events=True)
        for event in new_events:
            message += event.to_string()

        return message
    elif not silent:
        return messages_template.render(no_new_events=True)
    return None


def get_remind_message():
    event_list = create_event_list(cal_file_name)
    remind_list = []
    now = datetime.now(pytz.timezone(server_timezone))
    for event in event_list:
        start_time = event.time_start
        if start_time < now:
            pass

        seconds_left = (start_time - now).total_seconds()
        # TODO make the reminding time configurable
        if remind_time * 60 + check_interval / 2 > seconds_left > remind_time * 60 - check_interval / 2:
            remind_list.append(event)
    len_remind_list = len(remind_list)
    if len_remind_list is not 0:
        if len_remind_list == 1:
            return messages_template.render(reminder_single=True,
                                            events="\n".join(map(lambda evt: evt.to_string(), remind_list)))
        elif len_remind_list > 1:
            return messages_template.render(reminder_multiple=True,
                                            events="\n".join(map(lambda evt: evt.to_string(), remind_list)))
    return None


def overwrite_ics_file():
    with open(cal_file_name_new, 'r') as new_events_file:
        with open(cal_file_name, 'w+') as current_events_file:
            current_events_file.writelines(new_events_file)


def events(bot, update):
    message = get_events_diff(silent=False, return_all=True)
    send_message(bot, update.effective_chat.id, message)


def callback_interval(bot, job):
    events_sub_ids = get_chat_ids(sub_chat_ids_file_name)
    diff_events = get_events_diff()
    if diff_events is not None:
        for line in events_sub_ids:
            send_message(bot, int(line), diff_events)

    remind_sub_ids = get_chat_ids(remind_chat_ids_file_name)
    remind_message = get_remind_message()
    if remind_message is not None:
        for line in remind_sub_ids:
            send_message(bot, int(line), remind_message)

    overwrite_ics_file()


def get_chat_ids(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as file:
        return [str(line).replace('\n', '') for line in file]


def write_chat_ids(chat_ids, filename):
    with open(filename, 'w+') as file:
        file.write("\n".join(chat_ids))


def check_chat_id(chat_id, filename):
    return chat_id in get_chat_ids(filename)


def remove_chat_id(chat_id, filename):
    chat_ids = get_chat_ids(filename)
    chat_ids.remove(chat_id)
    write_chat_ids(chat_ids, filename)


def add_chat_id(chat_id, filename):
    chat_ids = get_chat_ids(filename)
    chat_ids.append(chat_id)
    write_chat_ids(chat_ids, filename)


def abo(bot, update, args):
    remove = False
    if len(args) == 1:
        if args[0] == "an":
            pass
        elif args[0] == "aus":
            remove = True
        else:
            print_unknown_command(bot, update.message.chat_id, "/abo", args)
    elif len(args) != 0:
        print_unknown_command(bot, update.message.chat_id, "/abo", args)

    chat_id = str(update.effective_chat.id)
    has_subscribed = check_chat_id(chat_id, sub_chat_ids_file_name)
    if has_subscribed and not remove:
        logger.debug("%s, %s tried to subscribe, but was already receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id, sub_unsub_template.render(invalid_sub=True))
    elif not has_subscribed and remove:
        logger.debug("%s, %s tried to unsubscribe, but was not receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id, sub_unsub_template.render(invalid_unsub=True))
    else:
        if remove:
            logger.debug("%s , %s unsubscribed", chat_id, update.effective_user.username)
            remove_chat_id(chat_id, sub_chat_ids_file_name)
            send_message(bot, update.message.chat_id, sub_unsub_template.render(unsub=True))
        else:
            logger.debug("%s , %s subscribed", chat_id, update.effective_user.username)
            add_chat_id(chat_id, sub_chat_ids_file_name)
            send_message(bot, update.message.chat_id, sub_unsub_template.render(sub=True))


def remind(bot, update, args):
    remove = False
    if len(args) == 1:
        if args[0] == "an":
            pass
        elif args[0] == "aus":
            remove = True
        else:
            print_unknown_command(bot, update.message.chat_id, "/erinnerung", args)
    elif len(args) != 0:
        print_unknown_command(bot, update.message.chat_id, "/erinnerung", args)

    chat_id = str(update.effective_chat.id)
    has_subscribed = check_chat_id(chat_id, remind_chat_ids_file_name)
    if has_subscribed and not remove:
        logger.debug("%s, %s tried to turn on reminder, but was already receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id, reminder_template.render(invalid_remind_on=True))
    elif not has_subscribed and remove:
        logger.debug("%s, %s tried to turn off reminder, but was not receiving notifications", chat_id,
                     update.effective_user.username)
        send_message(bot, update.message.chat_id, reminder_template.render(invalid_remind_off=True))
    else:
        if remove:
            logger.debug("%s , %s turned off reminder", chat_id, update.effective_user.username)
            remove_chat_id(chat_id, remind_chat_ids_file_name)
            send_message(bot, update.message.chat_id, reminder_template.render())
        else:
            logger.debug("%s , %s turned on reminder", chat_id, update.effective_user.username)
            add_chat_id(chat_id, remind_chat_ids_file_name)
            send_message(bot, update.message.chat_id, reminder_template.render(remind=True))


def print_status(bot, update):
    has_subscribed = str(update.message.chat_id) in get_chat_ids(sub_chat_ids_file_name)
    has_reminder = str(update.message.chat_id) in get_chat_ids(remind_chat_ids_file_name)
    status_message = status_template.render(
        notify=has_subscribed,
        remind=has_reminder
    )
    send_message(bot, update.message.chat_id, status_message)


def print_help(bot, update):
    help_message = help_template.render(
        appointments='termine',
        sub='abo',
        remind='erinnerung',
        status='status',
        help='hilfe'
    )
    send_message(bot, update.message.chat_id, help_message)


def unknown_command_callback(bot, update):
    print_unknown_command(bot, update.message.chat_id, update.message.text, [])


def print_version_info_if_needed(bot):
    print_version_text = True
    from __init__ import __version__
    if os.path.exists(version_file):
        with open(version_file, 'r') as file:
            version_string = file.read()
            if float(version_string) >= float(__version__):
                print_version_text = False

    if print_version_text:
        version_text = version_template.render(version=__version__)
        chat_ids = set().union(get_chat_ids(sub_chat_ids_file_name), get_chat_ids(remind_chat_ids_file_name))
        for chat_id in chat_ids:
            send_message(bot, int(chat_id), version_text)
        with open(version_file, 'w+') as file:
            file.write(__version__)


def main():
    updater = Updater(telegram_token)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('termine', events))
    dp.add_handler(CommandHandler('abo', abo, pass_args=True))
    dp.add_handler(CommandHandler('erinnerung', remind, pass_args=True))
    dp.add_handler(CommandHandler('status', print_status))
    dp.add_handler(CommandHandler('hilfe', print_help))
    dp.add_handler(CommandHandler('start', print_help))
    dp.add_handler(MessageHandler(Filters.command, unknown_command_callback))

    j = updater.job_queue
    j.run_repeating(callback_interval, interval=check_interval, first=0)

    print_version_info_if_needed(updater.bot)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
