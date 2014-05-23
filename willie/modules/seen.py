# coding=utf8
"""
seen.py - Willie Seen Module
Copyright 2008, Sean B. Palmer, inamidst.com
Copyright © 2012, Elad Alfassa <elad@fedoraproject.org>
Licensed under the Eiffel Forum License 2.

http://willie.dftba.net
"""
from __future__ import unicode_literals

import time
import datetime
from willie.tools import Ddict, Nick, get_timezone, format_time
from willie.module import commands, rule, priority

seen_dict = Ddict(dict)


def get_user_time(bot, nick, channel = None):
    tz = 'UTC'
    tformat = '%Y-%m-%d %H:%M:%S %Z'
    if bot.db and nick in bot.db.preferences:
        tz = bot.db.preferences.get(nick, 'tz') or 'UTC'
        tformat = bot.db.preferences.get(nick, 'time_format')
    elif channel and bot.db and channel in bot.db.preferences:
        tz = bot.db.preferences.get(channel, 'tz')

    tz = tz.strip()
    if tz not in pytz.all_timezones_set:
        tz = 'UTC'
    return pytz.timezone(tz), tformat


@commands('seen')
def seen(bot, trigger):
    """Reports when and where the user was last seen."""
    if not trigger.group(2):
        bot.say(".seen <nick> - Reports when <nick> was last seen.")
        return
    nick = Nick(trigger.group(2).strip())
    if nick in seen_dict:
        timestamp = seen_dict[nick]['timestamp']
        channel = seen_dict[nick]['channel']
        message = seen_dict[nick]['message']

        tz, tformat = get_user_time(bot, trigger.nick, trigger.sender)
        saw = datetime.datetime.fromtimestamp(timestamp, tz)
        timestamp = saw.strftime(tformat)

        msg = "I last saw %s at %s on %s, saying %s" % (nick, timestamp, channel, message)
        bot.say(str(trigger.nick) + ': ' + msg)
    else:
        bot.say("Sorry, I haven't seen %s around." % nick)


@rule('(.*)')
@priority('low')
def note(bot, trigger):
    if not trigger.is_privmsg:
        nick = Nick(trigger.nick)
        seen_dict[nick]['timestamp'] = time.time()
        seen_dict[nick]['channel'] = trigger.sender
        seen_dict[nick]['message'] = trigger
