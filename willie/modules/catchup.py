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
from time import sleep
from collections import deque
from willie.tools import Nick, WillieMemory
from willie.module import commands, rule, event, priority, unblockable, nickname_commands, NOLIMIT

queue_max = 10000
tformat = '%Y-%m-%d %H:%M'

class ChannelHistory:
    def __init__(self):
        self.count = 0
        self.history = deque( maxlen = queue_max)
        self.last_seen = WillieMemory()
        self.queue_lock = threading.Lock()

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
        bot.msg(nick, "You have to say .catchup in a channel I am monitoring")
        return

    info = bot.memory['catchup_info'][channel]

    total_messages = len(info.history)
    to_send = min(nMessages, total_messages)
    start = max(0, total_messages - to_send)

    messages = [info.history[i] for i in range(start, total_messages)]

    bot.msg(nick, 'Catchup on the last %d Messages from %s:' % (to_send, channel))
    for r in messages:
	sleep(0.2) # sleep 0.2 seconds between messages
        bot.msg(nick, r)

    #print('nMessages %d, total_messages %d, to_send %d, start %d, messagesLen %d' % (nMessages, total_messages, to_send, start, len(messages)))

def track_leave(bot, channel, nick):
    print("track_leave %s %s %s" % (bot, channel, nick))

    if not channel in bot.memory['catchup_info']:
        #print("channel not found - ignoring leave")
        return

    info = bot.memory['catchup_info'][channel]
    info.last_seen[nick] = info.count
    #print('%s left %s at %d' % (nick, channel, info.count))


def get_unseen_count(bot, channel, nick):
    if not channel in bot.memory['catchup_info']:
        return None

    info = bot.memory['catchup_info'][channel]
    if nick in info.last_seen:
        missed = info.count - info.last_seen[nick]
        return missed

    return None


@commands('catchup')
@nickname_commands('catchup')
def manual_catchup(bot, trigger):
    """ .catchup [n]: Manually catch up on missed messages OR the last n messages """
    asker = trigger.nick

    n = None
    nStr = trigger.group(2)
    if nStr:
        try:
            n = int(nStr)
        except ValueError:
            pass

    if not n and trigger.sender.startswith('#'):
        n = get_unseen_count(bot, trigger.sender, trigger.nick)

    if not n:
        n = 50

    send_history(bot, trigger.sender, asker, n)


@rule('(.*)')
@event('JOIN')
@priority('low')
@unblockable
def join(bot, trigger):
    # bot joins channel for the first time?
    if trigger.nick == bot.nick and not trigger.sender in bot.memory['catchup_info']:
        bot.memory['catchup_info'][trigger.sender] = ChannelHistory()
        return

    if not trigger.sender in bot.memory['catchup_info']:
        return

    info = bot.memory['catchup_info'][trigger.sender]
    missed = 50
    if trigger.nick in info.last_seen:
        missed = info.count - info.last_seen[trigger.nick]

    #send_history(bot, trigger.sender, trigger.nick, missed)

@rule('(.*)')
@event('PART')
@priority('low')
@unblockable
def part(bot, trigger):
    track_leave(bot, trigger.sender, trigger.nick)

@rule('(.*)')
@event('QUIT')
@priority('low')
@unblockable
def track_quit(bot, trigger):
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

    try:
        info.queue_lock.acquire()
        now = datetime.datetime.now(get_channel_time(bot, trigger.sender))
        record = '%s %s: %s' % (now.strftime(tformat), trigger.nick, trigger.group(0))
        info.history.append(record)
        info.count = info.count + 1
    finally:
        info.queue_lock.release()

    return NOLIMIT
