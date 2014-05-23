# coding=utf8
"""
tell.py - Willie Tell and Ask Module
Copyright 2008, Sean B. Palmer, inamidst.com
Licensed under the Eiffel Forum License 2.

http://willie.dftba.net
"""
from __future__ import unicode_literals

import os
import time
import datetime
import willie.tools
import threading
from willie.tools import Nick
from willie.module import commands, nickname_commands, rule, event, priority, example

maximum = 4


def loadReminders(fn, lock):
    lock.acquire()
    try:
        result = {}
        f = open(fn)
        for line in f:
            line = line.strip().decode('utf8')
            if line:
                try:
                    tellee, teller, verb, timenow, msg = line.split('\t', 4)
                except ValueError:
                    continue  # @@ hmm
                result.setdefault(tellee, []).append((teller, verb, timenow, msg))
        f.close()
    finally:
        lock.release()
    return result


def dumpReminders(fn, data, lock):
    lock.acquire()
    try:
        f = open(fn, 'w')
        for tellee in iterkeys(data):
            for remindon in data[tellee]:
                line = '\t'.join((tellee,) + remindon)
                try:
                    f.write((line + '\n').encode('utf-8'))
                except IOError:
                    break
        try:
            f.close()
        except IOError:
            pass
    finally:
        lock.release()
    return True


def setup(self):
    fn = self.nick + '-' + self.config.host + '.tell.db'
    self.tell_filename = os.path.join(self.config.dotdir, fn)
    if not os.path.exists(self.tell_filename):
        try:
            f = open(self.tell_filename, 'w')
        except OSError:
            pass
        else:
            f.write('')
            f.close()
    self.memory['tell_lock'] = threading.Lock()
    self.memory['reminders'] = loadReminders(self.tell_filename, self.memory['tell_lock'])


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


@commands('tell', 'ask')
@nickname_commands('tell', 'ask')
@example('Willie, tell Embolalia he broke something again.')
def f_remind(bot, trigger):
    """Give someone a message the next time they're seen"""
    teller = trigger.nick
    verb = trigger.group(1)

    if not trigger.group(3):
        bot.reply("%s whom?" % verb)
        return

    tellee = trigger.group(3).rstrip('.,:;')
    msg = trigger.group(2).lstrip(tellee).lstrip()

    if not msg:
        bot.reply("%s %s what?" % (verb, tellee))
        return

    tellee = Nick(tellee)

    if not os.path.exists(bot.tell_filename):
        return


    if len(tellee) > 20:
        return bot.reply('That nickname is too long.')
    if tellee == bot.nick:
        return bot.reply("I'm here now, you can tell me whatever you want!")

    if bot.privileges[trigger.sender] and tellee in bot.privileges[trigger.sender]:
        return bot.reply('%s is here right now, %s him yourself.' % (tellee, verb))

    if Nick(teller) == tellee:
        return bot.say('You can %s yourself that.' % verb)

    tz, tformat = get_user_time(bot, tellee, trigger.sender)
    timenow = datetime.datetime.now(tz).strftime(tformat)
    if not tellee in (Nick(teller), bot.nick, 'me'):
        tz = willie.tools.get_timezone(bot.db, bot.config, None, tellee)
        timenow = willie.tools.format_time(bot.db, bot.config, tz, tellee)
        bot.memory['tell_lock'].acquire()
        try:
            if not tellee in bot.memory['reminders']:
                bot.memory['reminders'][tellee] = [(teller, verb, timenow, msg)]
            else:
                bot.memory['reminders'][tellee].append((teller, verb, timenow, msg))
        finally:
            bot.memory['tell_lock'].release()

        response = "I'll pass that on when %s is around." % tellee

        bot.reply(response)
    else:
        bot.say("Hey, I'm not as stupid as Monty you know!")

    dumpReminders(bot.tell_filename, bot.memory['reminders'], bot.memory['tell_lock'])  # @@ tell


def getReminders(bot, channel, key, tellee):
    lines = []
    template = "%s: %s <%s> %s %s %s"
    today = time.strftime('%d %b', time.gmtime())

    bot.memory['tell_lock'].acquire()
    try:
        for (teller, verb, datetime, msg) in bot.memory['reminders'][key]:
            if datetime.startswith(today):
                datetime = datetime[len(today) + 1:]
            lines.append(template % (tellee, datetime, teller, verb, tellee, msg))

        try:
            del bot.memory['reminders'][key]
        except KeyError:
            bot.msg(channel, 'Er...')
    finally:
        bot.memory['tell_lock'].release()
    return lines


@rule('(.*)')
@event('JOIN')
@priority('low')
def message(bot, trigger):

    tellee = trigger.nick
    channel = trigger.sender

    if not os.path.exists(bot.tell_filename):
        return

    reminders = []
    remkeys = list(reversed(sorted(bot.memory['reminders'].keys())))

    for remkey in remkeys:
        if not remkey.endswith('*') or remkey.endswith(':'):
            if tellee == remkey:
                reminders.extend(getReminders(bot, channel, remkey, tellee))
        elif tellee.startswith(remkey.rstrip('*:')):
            reminders.extend(getReminders(bot, channel, remkey, tellee))

    for line in reminders[:maximum]:
        bot.say(line)

    if reminders[maximum:]:
        bot.say('Further messages sent privately')
        for line in reminders[maximum:]:
            bot.msg(tellee, line)

    if len(bot.memory['reminders'].keys()) != remkeys:
        dumpReminders(bot.tell_filename, bot.memory['reminders'], bot.memory['tell_lock'])  # @@ tell
