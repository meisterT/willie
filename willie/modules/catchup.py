"""
catchup.py - Willie IRC-History features
Copyright 2013, Demian Kellermann
Licensed under the Eiffel Forum License 2.
"""

import os
import time
import datetime
import pytz
import threading
import itertools
from collections import deque


from willie.tools import Nick
from willie.module import commands, rule, event, priority, nickname_commands, NOLIMIT

queue_max = 1000
tformat = '%Y-%m-%d %H:%M'

def setup(self):
    self.memory['catchup_history'] = deque(maxlen = queue_max)
    self.memory['catchup_last_seen'] = dict()
    self.memory['catchup_count'] = 0

def get_channel_time(bot, channel):
    tz = 'UTC'
    if channel and bot.db and channel in bot.db.preferences:
        tz = bot.db.preferences.get(channel, 'tz')

    tz = tz.strip()
    if tz not in pytz.all_timezones_set:
        tz = 'UTC'
    return pytz.timezone(tz)

def send_history(bot, nick, nMessages):

    total = bot.memory['catchup_count'];
    n = min(nMessages, total)

    if n < 1:
        return

    start = max(0, total - n)

    toSend = list(itertools.islice(bot.memory['catchup_history'], start, total))

    bot.msg(nick, 'Catchup on the last %d Messages:' % (total - start))
    for r in toSend:
        bot.msg(nick, r)



@commands('catchup')
@nickname_commands('catchup')
def manual_catchup(bot, trigger):
    """ .catchup [n]: Manually catch up on the last N messages """
    asker = trigger.nick

    n = None
    nStr = trigger.group(2);
    if nStr:
        try:
            n = int(nStr)
        except ValueError:
            pass

    if not n:
        n = 100
    # send private msg here

    send_history(bot, asker, n)


@rule('(.*)')
@event('JOIN')
@priority('low')
def join(bot, trigger):
    missed = 50
    if trigger.nick in bot.memory['catchup_last_seen']:
        missed = bot.memory['catchup_count'] - bot.memory['catchup_last_seen'][trigger.nick]

    send_history(bot, trigger.nick, missed)

@rule('(.*)')
@event('PART')
@event('QUIT')
@priority('low')
def gone(bot, trigger):
    bot.memory['catchup_last_seen'][trigger.nick] = bot.memory['catchup_count']

@rule('(.*)')
@priority('low')
def message(bot, trigger):
    if not trigger.sender.startswith('#'):
        return NOLIMIT
    if trigger.nick == bot.nick:
        return NOLIMIT

    now = datetime.datetime.now(get_channel_time(bot, trigger.sender))
    record = '%s %s: %s' % (now.strftime(tformat), trigger.nick, trigger.group(0));
    bot.memory['catchup_history'].append(record);
    bot.memory['catchup_count'] = bot.memory['catchup_count'] + 1

    return NOLIMIT
