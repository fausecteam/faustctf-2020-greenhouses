#!/usr/bin/env python3

import os
import dbus
import sys
import signal

from dbus.types import UnixFd
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from sudod import getClient, SERVICE_NAME, SERVICE_INTERFACE, GUARD_INTERFACE

import pwd, grp

as_user = "root"
as_group = None

while True:
    if len(sys.argv) >= 3 and sys.argv[1] == "-u":
            as_user = sys.argv[2]
            sys.argv[1:3] = []
    elif len(sys.argv) >= 3 and  sys.argv[1] == "-g":
            as_group = sys.argv[2]
            sys.argv[1:3] = []
    else:
        break
command_argv = sys.argv[1:]

if as_group is None:
    as_group = grp.getgrgid(pwd.getpwnam(as_user).pw_gid).gr_name

DBusGMainLoop(set_as_default=True)

system_bus = dbus.SystemBus()
#print("i am",system_bus.get_unique_name())

c = getClient(system_bus)

cwdfd = os.open(".", os.O_RDONLY)
dbus_cwd = UnixFd(cwdfd)
os.close(cwdfd)



loop = GLib.MainLoop()


peer = c.createSession(command_argv, as_user, as_group)
peer = system_bus.get_object(peer, "/guard")
peer = dbus.Interface(peer, GUARD_INTERFACE)

peer.simpleAuth()

peer.chdirFD(dbus_cwd)

for (key, val) in os.environ.items():
    try:
        peer.setEnv(key, val)
    except:
        pass

for fd in range(3):
    x = peer.connectFD(UnixFd(fd))
    peer.dupFD(x, fd)
    peer.closeFD(x)

def on_exit(status):
    # relay exit info by dying the same way
    if os.WIFEXITED(status):
        os._exit(os.WEXITSTATUS(status))
    if os.WIFSIGNALED(status):
        sig = os.WTERMSIG(status)
        try:
            signal.signal(sig, signal.SIG_DFL)
        except OSError: # KILL or STOP, they work anyways
            pass
        os.kill(os.getpid(), os.WTERMSIG(status))
    os.exit(1)

peer.connect_to_signal("exited", on_exit)

peer.run()
loop.run()
