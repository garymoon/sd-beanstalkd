#!/usr/bin/env python
#
# Copyright (c) 2012 Curve <justin@curvehq.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import socket
import sys
import telnetlib
import yaml
import time


class Beanstalkd:
    def __init__(self, agentConfig, checksLogger, rawConfig):
        self.agentConfig = agentConfig
        self.checksLogger = checksLogger
        self.rawConfig = rawConfig

        if self.agentConfig is None:
            self.set_default_config()

        if ('Beanstalkd' not in self.agentConfig):
            self.set_default_config()

    def set_default_config(self):
        self.agentConfig = {}
        self.agentConfig['Beanstalkd'] = {'host': 'localhost', 'port': '11300'}

    def get_stats(self):
        self.telnet_connection.write("stats\r\n")
        status = self.telnet_connection.read_until("\r\n", 1)

        if status is not None and 'OK' in status:
            response = self.telnet_connection.read_until("\n\r\n", 1)
            return yaml.load(response)
        else:
            sys.stderr.write("Beanstalkd error for 'stats' cmd: %s" % (status))
            return None

    def get_status(self):
        ts = str(int(time.time()))
        ts_len = str(len(ts))

        self.telnet_connection.write("use __monitor_test__\r\n")
        status_use = self.telnet_connection.read_until("\r\n", 1)
        if "USING" not in status_use:
            return { "status": "Couldn't use tube '__monitor_test__'"}

        self.telnet_connection.write("put 1 0 10 " + ts_len + "\r\n")
        self.telnet_connection.write(ts + "\r\n")
        status_put = self.telnet_connection.read_until("\r\n", 1)
        if "INSERTED" not in status_put:
            return { "status": "Couldn't insert job" }

        self.telnet_connection.write("watch __monitor_test__\r\n")
        status_watch = self.telnet_connection.read_until("\r\n", 1)
        if "WATCHING" not in status_watch:
            return { "status": "Couldn't watch tube '__monitor_test__'" }

        self.telnet_connection.write("reserve-with-timeout 1\r\n")
        status_reserve = self.telnet_connection.read_until("\r\n", 1)
        status_data = self.telnet_connection.read_until("\r\n", 1)
        if "RESERVED" not in status_reserve or ts not in status_data:
            return { "status": "Reserve failed" }

        self.telnet_connection.write("delete " + status_reserve.split(' ')[1] + "\r\n")
        status_delete = self.telnet_connection.read_until("\r\n", 1)
        if "DELETED" not in status_delete:
            return { "status": "Couldn't delete job" }

        return { "status": 1 }

    def run(self):
        payload = {}

        host = self.agentConfig['Beanstalkd']['host']
        port = int(self.agentConfig['Beanstalkd']['port'])

        try:
            self.telnet_connection = telnetlib.Telnet()
            self.telnet_connection.open(host, port)
        except socket.error, reason:
            sys.stderr.write("%s\n" % reason)
            sys.stderr.write("Is beanstalk running?\n")
            return { "status": "Beanstalk unreachable" }

        # Daemon status
        daemon_status = self.get_status()
        payload.update(daemon_status)

        # Main Beanstalkd stats
        stats = self.get_stats()
        payload.update(stats)

        self.telnet_connection.close()

        return payload

if __name__ == '__main__':
    import pprint
    plugin = Beanstalkd(None, None, None)
    pprint.pprint(plugin.run())

