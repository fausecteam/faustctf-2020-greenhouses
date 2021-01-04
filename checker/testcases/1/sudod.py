#!/usr/bin/env python3

import traceback
import os
import sys
from gi.repository import GLib
#from pydbus import SystemBus
import dbus
import dbus.service
import dbus.mainloop.glib
from dataclasses import dataclass
from typing import List, Tuple, Dict
import signal
import fcntl
import collections
import time
import secrets
import pwd
import grp

SERVICE_NAME = 'net.faustctf.SuDoD'
SERVICE_INTERFACE = SERVICE_NAME
OBJECT_PATH = "/" + SERVICE_NAME.replace(".", "/")

GUARD_INTERFACE = SERVICE_INTERFACE+".Guard"

@dataclass
class Command:
    argv: List[str]
    user: str
    group: str

class CommandGuard(dbus.service.Object):
    def __init__(self, bus, command, session, allowed_client):
        super().__init__(conn = bus, object_path = "/guard")

        self.allowed_env = "XAUTHORIZATION XAUTHORITY PS2 PS1 LS_COLORS KRB5CCNAME HOSTNAME DPKG_COLORS DISPLAY COLORS SSH_ORIGINAL_COMMAND".split()
        self.allowed_client = allowed_client
        self.command = command
        self.session = session
        

        self.polkit = dbus.Interface(
                bus.get_object("org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority")
                , "org.freedesktop.PolicyKit1.Authority")
        self.org_freedesktop_DBus = dbus.Interface(
            bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus"),
            "org.freedesktop.DBus")
        sudod = getClient(bus)


        self.authorized = None
        self.pid = None
        sender_uid = self.org_freedesktop_DBus.GetConnectionUnixUser(allowed_client)
        sender_user = pwd.getpwuid(sender_uid).pw_name
        self.sender_user = sender_user
        os.environ["SUDO_USER"] = sender_user

        # tell the server our busname, so it can return it to the client
        sudod.registerSession(session)
        
        # set the uid/gid now, so that chdirFD can do the correct permission check
        os.chdir("/")
        os.setgid(grp.getgrnam(command.group).gr_gid)
        os.setgroups(os.getgrouplist(command.user, os.getgid()))
        os.setuid(pwd.getpwnam(command.user).pw_uid)

    @dbus.service.method(GUARD_INTERFACE, out_signature = "b", in_signature="", sender_keyword = "sender")
    def polkitAuth(self, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        # start polkit authorization
        auth_details = {}
        for i,a in enumerate(self.command.argv):
            auth_details["argv_"+str(i)] = a

        auth_details["as_user"] = str(self.command.user)
        auth_details["as_group"] = str(self.command.group)
        (self.authorized, _, _) = self.polkit.CheckAuthorization(("system-bus-name", {"name":self.allowed_client}), "net.faustctf.SuDoD.RunCommand", auth_details, 1, self.session)
        return self.authorized
    
    @dbus.service.method(GUARD_INTERFACE, out_signature = "b", in_signature="", sender_keyword = "sender")
    def simpleAuth(self, sender):
        if self.command.user == self.sender_user and grp.getgrnam(self.command.group).gr_gid in os.getgrouplist(self.sender_user, pwd.getpwnam(self.sender_user).pw_gid):
            self.authorized = True
        elif self.sender_user == "root":
            self.authorized = True
        elif self.command.argv[0] in ["/opt/gh/sow.py", "/opt/gh/show.py"] and self.command.user == "greenhouses":
            self.authorized = True
        elif self.sender_user == "gate" and self.command.argv[0] == "/opt/bin/register.sh":
            self.authorized = True
        else:
            self.authorized = False
        return True


    @dbus.service.method(GUARD_INTERFACE, out_signature = "i", in_signature = "h", sender_keyword = "sender")
    def connectFD(self, fd, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        n = fd.take()
        return n

    @dbus.service.method(GUARD_INTERFACE, out_signature = "", in_signature = "i", sender_keyword = "sender")
    def closeFD(self, fd, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        os.close(fd)

    @dbus.service.method(GUARD_INTERFACE, out_signature = "", in_signature = "ii", sender_keyword = "sender")
    def dupFD(self, oldnum, newnum, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        os.dup2(oldnum, newnum)

    @dbus.service.method(GUARD_INTERFACE, out_signature = "", in_signature = "h", sender_keyword = "sender")
    def chdirFD(self, d, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        fd = d.take()
        os.fchdir(fd)
        os.close(fd)
    
    @dbus.service.method(GUARD_INTERFACE, out_signature = "", in_signature = "ss", sender_keyword = "sender")
    def setEnv(self, key, val, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        if not key in self.allowed_env:
            raise RuntimeError("Variable Forbidden")
        os.environ[key] = val


    @dbus.service.method(GUARD_INTERFACE, out_signature = "i", in_signature = "", sender_keyword = "sender")
    def run(self, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        if not self.authorized:
            raise RuntimeError("Not Authorized")

        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        pid = os.fork()
        if pid == 0:
            try:
                os.execvp(self.command.argv[0], self.command.argv)
            except Exception:
                os.write(2, f"Exception from SuDoD:\n{traceback.format_exc()}".encode())
            finally:
                # NEVER return/raise into server process!!
                os._exit(1)
        self.pid = pid

        # TODO: Hopefully this PRIORITY_HIGH means, that
        # the callback is performed before a dbus call to kill
        GLib.child_watch_add(GLib.PRIORITY_HIGH, pid, self.on_wait)

        return pid

    def on_wait(self, pid, exitstatus):
        self.exited(exitstatus)
        # we are done
        os._exit(0)
    
    @dbus.service.method(GUARD_INTERFACE, out_signature = "", in_signature = "i", sender_keyword = "sender")
    def kill(self, sig, sender):
        if sender != self.allowed_client: raise RuntimeError("No")
        if self.pid is not None:
            os.kill(self.pid, sig)

    @dbus.service.signal(GUARD_INTERFACE, signature="i")
    def exited(self, status):
        pass

class SuDoD(dbus.service.Object):
    def __init__(self, bus):
        self.bus = bus
        self.sessions = {}
        print("i am",bus.get_unique_name())
        super().__init__(object_path = OBJECT_PATH, conn = self.bus)
        self.org_freedesktop_DBus = dbus.Interface(
            bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus"),
            "org.freedesktop.DBus")
        # from `sudo sudo -V` on debian sid
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    @dbus.service.method(SERVICE_INTERFACE, out_signature = "s", in_signature = "asss", sender_keyword = "sender", async_callbacks = ("return_cb", "error_cb"))
    def createSession(self, argv, user, group, sender, return_cb, error_cb):
        print("createSession called from", sender)
        session = secrets.token_hex(16)
        self.sessions[session] = (return_cb, error_cb)

        pid = os.fork()
        print("forked, pid =", pid)
        if pid == 0:
            try:
                os.execlp(sys.executable, sys.executable, __file__, "--session", session, user, group, sender, *argv)
            except Exception:
                os.write(2, f"Exception from SuDoD:\n{traceback.format_exc()}".encode())
            finally:
                os._exit(0)

    @dbus.service.method(SERVICE_INTERFACE, out_signature = "", in_signature = "s", sender_keyword = "sender")
    def registerSession(self, session, sender):
        x = self.sessions[session]
        if isinstance(x, str): return
        (return_cb, error_cb) = self.sessions.pop(session)
        return_cb(sender)
    
    
        
#system_bus.publish(SERVICE_NAME, SuDoD())

def getClient(system_bus):
    o = system_bus.get_object(SERVICE_NAME, OBJECT_PATH)
    i = dbus.Interface(o, SERVICE_INTERFACE)
    return i


def guard_main():
    _me, _flag, session, user, group, sender, *argv = sys.argv
    command = Command(argv, user=user, group=group)
    loop = GLib.MainLoop()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    system_bus = dbus.SystemBus()
    g = CommandGuard(system_bus, command, session, sender)
    loop.run()

def server_main():

    loop = GLib.MainLoop()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    system_bus = dbus.SystemBus()
    name = dbus.service.BusName(SERVICE_NAME, bus = system_bus)
    sudod = SuDoD(system_bus)
    loop.run()

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(sys.argv) <= 1:
        server_main()
    elif sys.argv[1] == "--session":
        guard_main()
    else:
        print("invalid usage, please look at the code.")
        exit(1)

