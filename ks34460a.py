#!/usr/bin/env python3

import argparse
import json
import re
import sys
import time

try:
    import pyvisa
except ImportError:
    print("pyvisa not installed. Install with: pip install pyvisa pyvisa-py")
    sys.exit(1)

CONFIG = {
    'modes': {
        'volts_dc': {
            'cmd': 'VOLT:DC',
            'range': ['0.1', '1', '10', '100', '1000',
                'auto', 'min', 'max', 'def'],
            'nplc': ['0.02', '0.06', '0.2', '1', '2', '10', '100', 'min', 'max', 'def'],
        },
        'volts_ac': {
            'cmd': 'VOLT:AC',
            'range': ['0.1', '1', '10', '100', '750',
                'auto', 'min', 'max', 'def'],
            'bandwidth': ['3', '20', '200', 'min', 'max', 'def'],
        },
        'current_dc': {
            'cmd': 'CURR:DC',
            'range': ['0.0001', '0.001', '0.01', '0.1', '1', '3',
                'auto', 'min', 'max', 'def'],
            'nplc': ['0.02', '0.06', '0.2', '1', '2', '10', '100', 'min', 'max', 'def'],
        },
        'current_ac': {
            'cmd': 'CURR:AC',
            'range': ['1', '3', 'auto', 'min', 'max', 'def'],
            'bandwidth': ['3', '20', '200', 'min', 'max', 'def'],
        },
        'resistance': {
            'cmd': 'RES',
            'range': ['100', '1000', '10000', '100000', '1000000',
                '10000000', '100000000', '1000000000',
                'auto', 'min', 'max', 'def'],
            'nplc': ['0.02', '0.06', '0.2', '1', '2', '10', '100', 'min', 'max', 'def'],
        },
        'resistance_4w': {
            'cmd': 'FRES',
            'range': ['100', '1000', '10000', '100000', '1000000',
                '10000000', '100000000', '1000000000',
                'auto', 'min', 'max', 'def'],
            'nplc': ['0.02', '0.06', '0.2', '1', '2', '10', '100', 'min', 'max', 'def'],
        },
        'frequency': {
            'cmd': 'FREQ',
            'range': ['0.1', '1', '10', '100', '750', 'auto', 'min', 'max', 'def'],
        },
        'period': {
            'cmd': 'PER',
            'range': ['0.1', '1', '10', '100', '750', 'auto', 'min', 'max', 'def'],
        },
        'temperature': {
            'cmd': 'TEMP',
            'probe': ['RTD,85', 'THER,5000', 'THER,10000'],
        },
        'diode': {
            'cmd': 'DIOD',
        },
        'continuity': {
            'cmd': 'CONT',
        },
        'capacitance': {
            'cmd': 'CAP',
            'range': ['1e-9', '10e-9', '100e-9', '1e-6', '10e-6', '100e-6',
                '1e-3', '10e-3', 'auto', 'min', 'max', 'def'],
        },
    },
    'status': {
        'identity': '*IDN?',
        'mode': 'CONF?',
        'trigger_count': 'TRIG:COUN?',
        'trigger_delay': 'TRIG:DEL?',
        'trigger_slope': 'TRIG:SLOP?',
        'trigger_source': 'TRIG:SOUR?',
        'sample_count': 'SAMP:COUN?',
    }
}

DEBUG = False


def debugprint(*a, **d):
    if DEBUG:
        print(*a, **d)


class KSException(Exception):
    def __init__(self, message):
        super().__init__(message)


class KS34460A(object):

    def __init__(self, resource=None):
        self.rm = pyvisa.ResourceManager('@py')
        self.inst = None
        self._connect(resource)
        self.sample_count = int(self._send_and_read('SAMP:COUN?'))

    def _connect(self, resource=None):
        try:
            if resource is None:
                resources = self.rm.list_resources()
                usb_resources = [r for r in resources if 'USB' in r]
                if not usb_resources:
                    raise KSException(f'No USB instruments found. Available: {resources}')
                for r in usb_resources:
                    if '34460' in r or '34461' in r or 'KEYSIGHT' in r.upper():
                        resource = r
                        break
                if resource is None:
                    resource = usb_resources[0]
                print(f'Auto-selected: {resource}')

            self.inst = self.rm.open_resource(resource)
            self.inst.timeout = 10000
            self.inst.read_termination = '\n'
            self.inst.write_termination = '\n'
        except Exception as e:
            raise KSException(repr(e))

    def _send_command(self, command):
        debugprint(f' >> {command}')
        self.inst.write(command)

    def _read_response(self):
        try:
            line = self.inst.read()
        except Exception as e:
            raise KSException(f'Exception on read: {e}')
        debugprint(f' << {line}')
        line = line.strip()
        line = re.sub(r'^"(.*)"$', r'\1', line)
        return line

    def _send_and_read(self, command):
        debugprint(f' >> {command}')
        response = self.inst.query(command)
        debugprint(f' << {response}')
        return response.strip()

    def meas(self):
        if self.sample_count != 1:
            self._send_command('SAMP:COUN 1')
            self.sample_count = 1
        return float(self._send_and_read('READ?'))

    def measN(self, count=1):
        self._send_command(f'SAMP:COUN {count}')
        self.sample_count = count
        self._send_command('TRIG:COUN 1')
        self._send_command('TRIG:DEL 0')
        self._send_command('TRIG:SOUR IMM')
        r = [float(x) for x in self._send_and_read('READ?').split(',')]
        return r

    def reset(self):
        self._send_command('*RST')
        self._send_command('*CLS')

    def configure(self, mode='volts_dc', rnge=None, nplc=None):
        if mode not in CONFIG['modes']:
            m = ','.join(CONFIG['modes'].keys())
            raise KSException(f'mode should be one of: {m}')

        mode_config = CONFIG['modes'][mode]

        if rnge is not None:
            rnge = rnge.lower()
            if 'range' in mode_config and rnge not in mode_config['range']:
                rs = ','.join(mode_config['range'])
                raise KSException(f'range should be one of {rs}')

        c = mode_config['cmd']
        if rnge is not None and rnge != 'auto':
            self._send_command(f'CONF:{c}')
            self._send_command(f'{c}:RANG {rnge}')
        elif rnge == 'auto':
            self._send_command(f'CONF:{c}')
            self._send_command(f'{c}:RANG:AUTO ON')
        else:
            self._send_command(f'CONF:{c}')

        if nplc is not None:
            if 'nplc' not in mode_config:
                raise KSException(f'NPLC not supported for mode {mode}')
            if nplc not in mode_config['nplc']:
                raise KSException(f'inappropriate nplc value for mode {mode}')
            c = mode_config['cmd']
            self._send_command(f'{c}:NPLC {nplc}')

    def getStatus(self):
        r = {i[0]: self._send_and_read(i[1]) for i in CONFIG['status'].items()}
        return r

    def list_resources(self):
        return self.rm.list_resources()

    def close(self):
        if self.inst:
            self.inst.close()


def list_modes():
    return sorted(CONFIG['modes'].keys())


def list_ranges():
    rdict = {}
    for v in CONFIG['modes'].values():
        if 'range' in v:
            rdict.update({x: 1 for x in v['range']})
    return sorted(rdict.keys(), key=lambda x: (x.replace('.', '').replace('-', '').isdigit(), x))


def list_nplcs():
    ndict = {}
    for v in CONFIG['modes'].values():
        if 'nplc' in v:
            ndict.update({x: 1 for x in v['nplc']})
    return sorted(ndict.keys(), key=lambda x: (x.replace('.', '').isdigit(), x))


def command():

    def parse():
        parser = argparse.ArgumentParser(sys.argv[0])
        parser.add_argument(
            '--config', '-c',
            help='Configure the DMM',
            choices=list_modes(),
            type=str,
            action='store',
            default=None
        )

        parser.add_argument(
            '--range', '-r',
            help='Configure mode range',
            choices=list_ranges(),
            type=str,
            action='store',
            default=None
        )

        parser.add_argument(
            '--nplc', '-n',
            help='Configure nplc count',
            choices=list_nplcs(),
            type=str,
            action='store',
            default=None
        )

        parser.add_argument(
            '--resource', '-u',
            help='VISA resource string (e.g., USB0::0x2A8D::0x0201::...::INSTR)',
            type=str,
            action='store',
            default=None
        )

        parser.add_argument(
            '--list', '-L',
            help='List available VISA resources',
            action='store_true',
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
            default=0,
        )

        parser.add_argument(
            '--reset',
            help='reset the instrument',
            action='store_true',
        )

        parser.add_argument(
            '--loopdelay', '-l',
            help='loop with delay <n>',
            type=float,
            action='store',
            default=0,
        )

        parser.add_argument(
            '--raw',
            help='send a command directly to the dmm',
            type=str,
            action='store',
            default=None,
        )

        return parser.parse_args()

    args = parse()

    if args.list:
        rm = pyvisa.ResourceManager('@py')
        resources = rm.list_resources()
        print("Available VISA resources:")
        for r in resources:
            print(f"  {r}")
        return

    s = KS34460A(args.resource)

    if args.reset:
        s.reset()

    if args.config is not None:
        s.configure(args.config, args.range, args.nplc)

    if args.raw is not None:
        if '?' in args.raw:
            print(s._send_and_read(args.raw))
        else:
            s._send_command(args.raw)

    if args.status:
        print(json.dumps(s.getStatus(), indent=2))

    if args.loopdelay > 0:
        while True:
            print(s.meas())
            time.sleep(args.loopdelay)
    elif args.meas == 1:
        print(s.meas())
    elif args.meas > 1:
        print(json.dumps(s.measN(args.meas), indent=2))

    s.close()


if __name__ == '__main__':
    command()
