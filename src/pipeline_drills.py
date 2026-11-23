"""Explicit test hooks restricted to disposable databases under tmp/m5/."""
from pathlib import Path
import time

from db import ROOT


def add_arguments(parser):
    parser.add_argument('--drill-fail-after',type=int,help='Test only: fail after N row writes')
    parser.add_argument('--drill-sleep',type=float,default=0,help='Test only: sleep before work')


def guard(args):
    if args.drill_fail_after is None and args.drill_sleep==0:
        return
    path = Path(args.db).resolve()
    if not path.is_relative_to((ROOT/'tmp/m5').resolve()):
        raise ValueError('Drill hooks refuse production DBs; use a disposable DB under tmp/m5')
    if args.drill_sleep<0 or (args.drill_fail_after is not None and args.drill_fail_after<0):
        raise ValueError('Drill values must be nonnegative')
    if args.drill_sleep:
        time.sleep(args.drill_sleep)
