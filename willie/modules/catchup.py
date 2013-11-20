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
from willie.tools import Nick, WillieMemory
from willie.module import commands, rule, event, priority, unblockable, nickname_commands, NOLIMIT

queue_max = 1000
tformat = '%Y-%m-%d %H:%M'

class ChannelHistory:
    def __init__(self):
        self.count = 0
        self.history = deque( maxlen = queue_max)
        self.last_seen = WillieMemory()

def setup(self):
    self.memory['catchup_info'] = WillieMemory()

def get_channel_time(bot, channel):
    tz = 'UTC'
    if channel and bot.db and channel in bot.db.preferences:
        tz = bot.db.preferences.get(channel, 'tz')

    tz = tz.strip()
    if tz not in pytz.all_timezones_set:
        tz = 'UTC'
    return pytz.timezone(tz)

def send_history(bot, channel, nick, nMessages):
    if not channel in bot.memory['catchup_info']:
        bot.msg(nick, "Sorry, I don't seem to have history for this channel yet")
        return

    info = bot.memory['catchup_info'][channel]

    total = info.count
    n = min(nMessages, total)

    if n < 1:
        return

    start = max(0, total - n)

    toSend = list(itertools.islice(info.history, start, total))

    bot.msg(nick, 'Catchup on the last %d Messages from %s:' % (total - start, channel))
    for r in toSend:
        bot.msg(nick, r)

def track_leave(bot, channel, nick):
    if not channel.startswith('#'):
        return
    if not channel in bot.memory['catchup_info']:
        return

    info = bot.memory['catchup_info'][channel]
    info.last_seen[nick] = info.count


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

    send_history(bot, trigger.sender, asker, n)
    


@rule('(.*)')
@event('JOIN')
@priority('low')
@unblockable
def join(bot, trigger):
    # bot joins channel
    if trigger.nick == bot.nick:
        bot.memory['catchup_info'][trigger.sender] = ChannelHistory()
        return

    if not trigger.sender in bot.memory['catchup_info']:
        return

    info = bot.memory['catchup_info'][trigger.sender]
    missed = 50
    if trigger.nick in info.last_seen:
        missed = info.count - info.last_seen[trigger.nick]

    send_history(bot, trigger.sender, trigger.nick, missed)

@rule('(.*)')
@event('PART')
@event('KICK')
@priority('low')
@unblockable
def part(bot, trigger):
    track_leave(bot, trigger.sender, trigger.nick)

@rule('(.*)')
@event('QUIT')
@priority('low')
@unblockable
def quit(bot, trigger):
	for channel in bot.memory['catchup_info']:
		track_leave(bot, channel, trigger.nick)

@rule('(.*)')
@event('KICK')
@priority('low')
@unblockable
def kicked(bot, trigger):
    nick = Nick(trigger.args[1])
    track_leave(bot, trigger.sender, nick)

@rule('(.*)')
@priority('low')
@unblockable
def message(bot, trigger):
    if not trigger.sender.startswith('#'):
        return NOLIMIT

    # race with JOIN?
    if not trigger.sender in bot.memory['catchup_info']:
        return

    info = bot.memory['catchup_info'][trigger.sender]

    now = datetime.datetime.now(get_channel_time(bot, trigger.sender))
    record = '%s %s: %s' % (now.strftime(tformat), trigger.nick, trigger.group(0));
    info.history.append(record);
    info.count = len(info.history)

    return NOLIMIT
