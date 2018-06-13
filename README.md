# Documentation of the ICS-Telegram-Notification-Bot

## Installation

To install this bot on a machine, run `python3 setup.py install --user`. This installs all the needed dependencies,
creates a local `logs/`-folder for a debug-log and puts two configuration-files in the working directory.

## Configuration

There are multiple parameters to configure this bot:

### Inputparameters

#### `public_config.py`

| configuration_key | default | description |
|:-----------------:|:-------:|:-----------:|
| cal_url | / | Put your URL outputting an ICS-file here |
| check_interval | 60 | This parameter defines the interval (in seconds) in which the bot checks for an updated ICS-file | 
| cal_file_name | calendar.ics | This parameter defines the filename to which the bot saves the productive ICS-file |
| cal_file_name_new | calendar.ics.new | The bot uses this filename to store working ICS-files to it, so it can calculate a diff between the old calendar entries and potential new ones |
| chat_ids_file_name | chat_ids.txt | This filename is being used to store all chat-ids that have to be notified, when the calendar changes |
| server_timezone | Europe/Berlin | The timezone which is used to convert and display dates and times the correct way |

#### `private_config.py`

| configuration_key | default | description |
|:-----------------:|:-------:|:-----------:|
| telegram_token | / | Put your telegram bot API-Token here to verify, which bot you are |

### Logging

The default logging configuration uses two different handlers. One handler is a handler that writes out every message 
greater or equal to the level INFO to `stdout`. The other handler writes a debug-log to logs/debug.log. If you encounter
problems, you can consult that log. If you want to change the existing logging configuration, please consult the official
[documentation](https://docs.python.org/3/howto/logging.html) of logging in python

## Usage of the Bot in Telegram

The Bot currently supports three commands in the telegram-chat:
- `/termine` prints all upcoming events
- `/abo` adds the user to the list of subscribers and notifies the user when a new event arrives
- `/deabo` removes the user from the list of subscribers