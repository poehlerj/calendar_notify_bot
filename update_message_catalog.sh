#/usr/bin/env sh

./setup.py extract_messages --output-file calendar_bot/locales/messages.po
./setup.py update_catalog -l de -i calendar_bot/locales/messages.po -o calendar_bot/locales/de/LC_MESSAGES/messages.po

