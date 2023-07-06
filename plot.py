#!/usr/bin/env python3

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import datetime
import math, argparse, sys

import sdm3055

def getArgs():
    parser = argparse.ArgumentParser(sys.argv[0])

    parser.add_argument(
        '--address', '-a',
        help='SDM3055 IP Address',
        type=str,
        action='store',
        default='192.168.1.98'
    )

    parser.add_argument(
        '--mode', '-m',
        help='DMM Mode',
        choices=sdm3055.list_modes(),
        type=str,
        action='store',
        default='current_dc',
    )

    parser.add_argument(
        '--range', '-r',
        help='DMM Range',
        choices=sdm3055.list_ranges(),
        type=str,
        action='store',
        default='auto',
    )

    parser.add_argument(
        '--nplc', '-n',
        help='NPLC Speed',
        choices=sdm3055.list_nplcs(),
        type=str,
        action='store',
        default='10',
    )

    parser.add_argument(
        '--log', '-l',
        help='Log10 yrange',
        action='store_true',
    )

    parser.add_argument(
        '--width', '-w',
        help='width in _Samples_',
        action='store',
        type=int,
        default='500',
    )

    parser.add_argument(
        '--save', '-s',
        help='save to file',
        action='store',
        type=argparse.FileType('w'),
        nargs='?',
    )
    return parser.parse_args()



def start_plotter(s, args):
    x_data = []
    y_data = []

    fig   = plt.figure()
    line, = plt.plot_date(x_data, y_data, '-')

    if args.log:
        plt.yscale('symlog')
        plt.grid(True, which='both', ls='-')

    def update(frame):
        while len(x_data) > args.width:
            x_data.pop(0)
        while len(y_data) > args.width:
            y_data.pop(0)

        t = datetime.datetime.now()
        x_data.append(t)

        nv = s.meas() * 1000
        if args.save is not None:
            args.save.write(','.join((t.isoformat(), str(nv), '\n')))

        y_data.append(nv)
        line.set_data(x_data, y_data)
        fig.gca().relim()
        fig.gca().autoscale_view()
        return line,

    anim = FuncAnimation(fig, update, interval=1)
    plt.show()



PLOT_WIDTH_ITEMS = 500

if __name__ == '__main__':
    a = getArgs()
    s = sdm3055.SDM3055(a.address)
    s.configure(a.mode, a.range, a.nplc)
    start_plotter(s, a)

