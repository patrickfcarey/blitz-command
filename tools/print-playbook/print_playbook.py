#!/usr/bin/env python3
# FLEET-TOOLS-FORWARDER: this tool's code lives in fleet-tools-index (the fleet's tools monorepo) at
#   tools/blitz-command/tools/print-playbook/print_playbook.py
# Edit it THERE. This file runs that code in place, so every old caller of tools/print-playbook/print_playbook.py keeps working.
# Search: $FLEET_TOOLS if set (only it), else ~/github/trunk/fleet-tools-index, ~/fleet-tools-index, /turret/ai_workspace/fleet-tools-index, then ../fleet-tools-index beside this repo's checkout (from this file's real path, only when it runs as itself) and ../trunk/fleet-tools-index from there (a ~/github/worktrees worktree): the first that holds the file.
# FLEET_FORWARDER_PROBE=1 prints the file it would run and exits 0. Written by fleet-tools-index tix.py move.
import os as _ft_os, sys as _ft_sys
_FT_REL = 'tools/blitz-command/tools/print-playbook/print_playbook.py'
def _ft_find(rel):
    env = _ft_os.environ.get('FLEET_TOOLS')
    here = None if env else globals().get('__file__')
    here = here if here and _ft_os.path.basename(here) == 'print_playbook.py' else None
    up = _ft_os.path.join(_ft_os.path.dirname(_ft_os.path.realpath(here)), *['..'] * 3) if here else ''
    roots = [env] if env else [_ft_os.path.expanduser(r) for r in ['~/github/trunk/fleet-tools-index', '~/fleet-tools-index', '/turret/ai_workspace/fleet-tools-index']]
    roots += [] if env else [_ft_os.path.normpath(_ft_os.path.join(up, s)) for s in ['fleet-tools-index', '../trunk/fleet-tools-index'] if up]
    for r in roots:
        p = _ft_os.path.join(r, rel)
        if _ft_os.path.isfile(p):
            return p
    _ft_sys.stderr.write('%s: FLEET-TOOLS-FORWARDER: %s is in none of %s\n  fix: git -C <checkout> pull --ff-only (an old checkout lacks the file); no checkout: git clone git@github.com:patrickfcarey/fleet-tools-index.git ~/github/trunk/fleet-tools-index (dev box; the rig: ~/fleet-tools-index; the NAS: /turret/ai_workspace/fleet-tools-index); or FLEET_TOOLS=<checkout>\n' % (globals().get('__file__', '<no __file__>'), rel, roots))
    _ft_sys.exit(127)
_FT_REAL = _ft_find(_FT_REL)
if __name__ == '__main__' and _ft_os.environ.get('FLEET_FORWARDER_PROBE'):
    print(_FT_REAL)
    _ft_sys.exit(0)
with open(_FT_REAL, 'rb') as _ft_f:
    _ft_code = compile(_ft_f.read(), _FT_REAL, 'exec', dont_inherit=True)
del _ft_f, _ft_find, _ft_os, _ft_sys
exec(_ft_code)
