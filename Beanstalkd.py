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


class Beanstalkd:
    def __init__(self, agentConfig, checksLogger, rawConfig):
        self.agentConfig = agentConfig
        self.checksLogger = checksLogger
        self.rawConfig = rawConfig

        if self.agentConfig is None:
            self.set_default_config()

        if ('Beanstalk' not in self.agentConfig):
            self.set_default_config()

    def set_default_config(self):
        self.agentConfig = {}
        self.agentConfig['Beanstalk'] = {'host': 'localhost', 'port': '11300'}

    def connect(self):
        host = self.agentConfig['Beanstalk']['host']
        port = int(self.agentConfig['Beanstalk']['port'])

        try:
            self.telnet_connection = telnetlib.Telnet()
            self.telnet_connection.open(host, port)
        except socket.error, reason:
            sys.stderr.write("%s\n" % reason)
            sys.stderr.write("Is beanstalk running?\n")
            raise # re-raise caught exception, sd-agent will catch it

    def disconnect(self):
        self.telnet_connection.close()

    def interact(self, cmd):
        self.telnet_connection.write('%s\r\n' % cmd)
        status = self.telnet_connection.read_until("\r\n")

        if status is not None and 'OK' in status:
            response = self.telnet_connection.read_until("\n\r\n")
            return yaml.load(response)
        else:
            sys.stderr.write("Beanstalkd error for cmd (%s): %s" % (cmd, status))
            return None

    def get_stats(self):
        return self.interact('stats')

    def get_tubes_list(self):
        return self.interact('list-tubes')

    def prefix_keys(self, tube_name, stats):
        '''
        Our plugin output must be a flat dict. Since each tube returns the
        same key/value stats we must prefix key names with the tube name e.g.
        the key total-jobs for tube 'email_signup' becomes email_signup-total-jobs.
        '''
        new_dict = {}

        # SD does not allow full stop (period) characters in key names
        # http://support.serverdensity.com/knowledgebase/articles/76015-plugin-restrictions
        tube_name = tube_name.replace('.', '_')

        for k, v in stats.items():
            key = '%s-%s' % (tube_name, k)
            new_dict[key] = v

        return new_dict

    def get_tube_stats(self):
        stats = {}
        for tube in self.get_tubes_list():
            tube_stats = self.interact('stats-tube %s' % tube)
            tube_stats = self.prefix_keys(tube, tube_stats)
            stats.update(tube_stats)

        return stats

    def run(self):
        payload = {}
        
        self.connect()

        # Main Beanstalkd stats
        stats = self.get_stats()
        payload.update(stats)

        # Tube stats
        tube_stats = self.get_tube_stats()
        payload.update(tube_stats)

        self.disconnect()
        return payload

if __name__ == '__main__':
    import pprint
    plugin = Beanstalk(None, None, None)
    pprint.pprint(plugin.run())
