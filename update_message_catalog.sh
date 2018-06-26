#!/usr/bin/env sh

if [ -n "$1" ] && [ "$1" == "generate" ]; then
    ./setup.py extract_messages --output-file calendar_bot/locales/messages.po
    ./setup.py update_catalog -l de -i calendar_bot/locales/messages.po -o calendar_bot/locales/de/LC_MESSAGES/messages.po
else
    ./setup.py compile_catalog --directory calendar_bot/locales --locale de
fi