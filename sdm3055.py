#!/usr/bin/env python3

import argparse
import json
import re
import socket
import sys

CONFIG = {
    'modes': {
        'volts_dc': {
            'cmd': 'VOLT:DC',
            'range': ['200mv', '2v', '20v', '200v', '1000v',
                'auto', 'min', 'max', 'def' ],
        },
        'volts_ac': {
            'cmd': 'VOLT:AC',
            'range': ['200mv', '2v', '20v', '200v', '1000v',
                'auto', 'min', 'max', 'def' ],
        },
        'current_dc': {
            'cmd': 'CURR:DC',
            'range': ['200ua', '2ma', '20ma', '200ma', '2a', '10a',
                'auto', 'min', 'max', 'def' ],
        },
        'current_ac': {
            'cmd': 'CURR:AC',
            'range': ['20ma', '200ma', '2a', '10a',
                'auto', 'min', 'max', 'def' ],
        },
        'temperature': {
            'cmd': 'TEMP',
            'range': ['RTD,PT100', 'RTD,PT1000', 'THER,BITS90','THER,EITS90',
                'THER,JITS90','THER,NITS90', 'THER,SITS90', 'THER,TITS90', ],
        },
        'resistance': {
            'cmd': 'RES',
            'range': ['200', '2k', '20k', '200k', '2m', '10m', '100m',
                'auto', 'min', 'max', 'def' ],
        },
        'resistance_4w': {
            'cmd': 'FRES',
            'range': ['200', '2k', '20k', '200k', '2m', '10m', '100m',
                'auto', 'min', 'max', 'def' ],
        },
        'frequency': {
            'cmd': 'FREQ',
            'range': [],
        },
        'diode': {
            'cmd': 'DIOD',
            'range': [],
        },
        'continuity': {
            'cmd': 'CONT',
            'range': [],
        },
    },
    'status': {
        'identity': '*IDN?',
        'mode': 'CONF?',
        'sense': 'SENSE:FUNC?',
        'trigger_count': 'TRIG:COUN?',
        'trigger_delay': 'TRIG:DEL?',
        'trigger_slope': 'TRIG:SLOP?',
        'trigger_source': 'TRIG:SOUR?',
        'sample_count': 'SAMP:COUN?',
    }
}

class SDMException(Exception):
    def __init__(self, message):
        super().__init__(message)


class SDM3055(object):

    def __init__(self, ip):
        self.ip = ip
        self.port = 5025
        self.s = None
        self.sf = None
        self._connect()
        self.sample_count = int(self._send_and_read('SAMP:COUN?'))

    def _connect(self):
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((self.ip, self.port))
            self.sf = self.s.makefile('rb', errors='replace')
        except Exception as e:
            raise SDMException(repr(e))

    def _send_command(self, command):
        os = command.encode('ascii', errors='none')
        print(f' >> {os}')
        self.s.sendall(os + b'\n')

    def _read_response(self):
        try:
            line = self.sf.readline()
            if isinstance(line, bytes):
                line = line.decode('ascii', errors='replace')
        except Exception as e:
            raise SDMException(f'Exception on stream: {e}')
            self.sf.close()
            return None
        if not line:
            self.sf.close()
            return None
        print(f' << {line}')
        line = line.strip()
        line = re.sub(r'^"(.*)"$', r'\1', line)
        return line

    def _send_and_read(self, command):
        self._send_command(command)
        return self._read_response()

    def meas(self):
        if self.sample_count != 1:
            self._send_command('SAMP:COUN 1')
            self.sample_count = 1
        self._send_command('READ?')
        return float(self._read_response())

    def measN(self, count=1):
        self._send_command(f'SAMP:COUN {count}')
        self.sample_count = count
        self._send_command('TRIG:COUN 1')
        self._send_command('TRIG:DEL 0')
        self._send_command('TRIG:SOUR IMM')
        self._send_command('READ?')
        r = [ float(x) for x in self._read_response().split(',') ]
        return r

    def reset(self):
        self._send_command('*RST')

    def configure(self, mode='volts_dc', rnge=None):
        if mode not in CONFIG['modes']:
            m = ','.join(CONFIG['modes'].keys())
            raise SDMException(f'mode should be one of: {m}')
        if rnge is not None:
            rnge = rnge.lower()
            if rnge not in CONFIG['modes'][m]['range']:
                rs = ','.join(CONFIG['modes'][m]['range'])
                raise SDMException(f'second argument should be on of {rs}')

        c = CONFIG['modes'].get(mode)['cmd']
        if rnge is not None:
            c += f' {rnge}'
        self._send_command(f'CONF:{c}')

    def getStatus(self):
        r = { i[0]: self._send_and_read(i[1]) for i in CONFIG['status'].items() }
        return r


def command():
    
    def parse():
        parser = argparse.ArgumentParser(sys.argv[0])
        parser.add_argument(
            '--config', '-c',
            help='Configure the DMM',
            choices=CONFIG['modes'].keys(),
            type=str,  
            action='store',
            default=None
        )

        rdict = {}
        for v in CONFIG['modes'].values():
            rdict.update({ x:1 for x in v['range']})

        parser.add_argument(
            '--range', '-r',
            help='Configure mode range',
            choices=sorted(rdict.keys()),
            type=str,  
            action='store',
            default=None
        )

        parser.add_argument(
            '--ip', '-i',
            help='IP address',
            type=str,
            action='store',
            default='192.168.1.98'
        )
        
        parser.add_argument(
            '--status', '-s',
            help='Get instrument status',
            action='store_true',
        )

        parser.add_argument(
            '--meas', '-m',
            help='Measurements to get',
            action='store',
            type=int,
            default=1,
        )

        parser.add_argument(
            '--reset',
            help='reset the instrument',
            action='store_true',
        )

        return parser.parse_args()

    args = parse()

    s = SDM3055(args.ip)

    if args.reset:
        s.reset()

    if args.config is not None:
        s.configure(args.config, args.range)

    if args.status:
        print(json.dumps(s.getStatus(), indent=2))

    if args.meas == 1:
        print(s.meas())
    elif args.meas > 1:
        print(json.dumps(s.measN(args.meas), indent=2))


if __name__ == '__main__':

    if True:
        command()
    else:
        s = SDM3055('192.168.1.98')
        print(s.getStatus())
        m = s.meas()
        print(m)
        s.configure('volts_dc')
        m = s.meas()
        print(m)
        s.configure('current_dc')
        m = s.measN(count=10)
        print(m)
