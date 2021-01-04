#!/usr/bin/env python3

from ctf_gameserver import checkerlib

import utils

import os
import paramiko.client
import paramiko.ed25519key
import paramiko.ssh_exception
import tempfile
import base64
import subprocess
import hashlib
import logging
import io
import tarfile

class AcceptAll(paramiko.client.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        return

def genkey():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "key")
        subprocess.check_call(["ssh-keygen", "-f", f, "-q", "-t", "ed25519", "-N", ""])
        with open(f) as x: text = x.read()
        k = paramiko.ed25519key.Ed25519Key(filename=f)
    return text, k

def loadkey(text):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "key")
        with open(f,"w") as x: x.write(text)
        k = paramiko.ed25519key.Ed25519Key(filename=f)
    return k

def register_user(ip):
    text,k = genkey()
    pub = base64.b64encode(k.asbytes())
    c = paramiko.client.SSHClient()
    c.set_missing_host_key_policy(AcceptAll())
    try:
        c.connect(ip, 2222, username="gate", password="", timeout=20, auth_timeout = 20, banner_timeout=20)
    except paramiko.ssh_exception.SSHException:
        raise Down()
    stdin, stdout, stderr = c.exec_command(pub)
    stdin.close()
    garbage = stderr.read()
    logging.info("stderr is %s" % garbage)
    line = stdout.read()
    logging.info("line is %s" %line)
    try:
        stderr.close()
        stdout.close()
        c.close()
    except: pass
    try:
        user = line.decode().strip().split()[-1]
    except:
        raise Faulty()
    logging.info("registered as '%s'" %user)
    return user, k, text

def state_connection(ip, name):
    text = checkerlib.load_state(name)
    if text is None:
        logging.info("registering user for connection %s"%(name))
        user,k,text = register_user(ip)
        checkerlib.store_state(name, text)
    else:
        k = loadkey(text)
        pub = base64.b64encode(k.asbytes())
        user = "user" + hashlib.sha256(pub+b"\n").hexdigest()[:28]
        logging.info("restored username '%s' for connection %s" %(user, name))
    return connect(ip, user, k)

def connect(ip, user, k):
    c = paramiko.client.SSHClient()
    c.set_missing_host_key_policy(AcceptAll())
    c.connect(ip, 2222, username=user, pkey = k, timeout=20, banner_timeout=20, auth_timeout=20)
    return c


def run_testcase(ip, tc, expect):
    buf = io.BytesIO()
    source_dir = os.path.join(os.path.dirname(__file__), "testcases", tc)
    with tarfile.open(fileobj = buf, mode="w") as tar:
        tar.add(source_dir, arcname=".")

    logging.info("registering user to run testcase %s" % tc)
    user,k,text = register_user(ip)
    logging.info("connecting to run testcase %s" % tc)
    try:
        c = connect(ip, user, k)
        logging.info("running command for testcase %s" % tc)
        stdin, stdout, stderr = c.exec_command("umask 077; tar x; ./runme 2>&1")
        logging.info("sending tar for testcase %s" % tc)
        stdin.write(buf.getvalue())
        logging.info("reading output for testcase %s" % tc)
        text = stdout.read()
        stderr.close()
        try:
            stderr.close()
            stdout.close()
            c.close()
        except: pass
        if text.strip() == expect.encode().strip():
            logging.info("got expected result for testcase %s" % tc)
            return True
        else:
            logging.info("got UNEXPECTED result for testcase %s: %s" % (tc, text))
            return False
    except paramiko.ssh_exception.SSHException:
        return False




class Down(Exception):
    pass
class Faulty(Exception):
    pass

def trywrapper(f):
    def g(*args):
        try:
            return f(*args)
        except Faulty:
            return checkerlib.CheckResult.FAULTY
        except Down:
            return checkerlib.CheckResult.DOWN
        except paramiko.ssh_exception.SSHException:
            return checkerlib.Checker.DOWN
    return g

class Checker(checkerlib.BaseChecker):
    @trywrapper
    def place_flag(self, tick):
        logging.info("connecting to place flag %s" % checkerlib.get_flag(tick))
        try:
            c = state_connection(self.ip, str(tick))
        except Down:
            return checkerlib.CheckResult.DOWN
        except paramiko.ssh_exception.SSHException:
            return checkerlib.CheckResult.FAULTY
        except Faulty:
            return checkerlib.CheckResult.FAULTY
        except Down:
            return checkerlib.CheckResult.DOWN
        logging.info("running sow")
        stdin, stdout, stderr = c.exec_command("/opt/bin/ghsow")
        stdin.write(checkerlib.get_flag(tick) + "\n")
        stdin.close()
        logging.info("flag sent, lets see the output:")
        logging.info("stdout: %s" % stdout.read())
        logging.info("stderr: %s" % stderr.read())
        try:
            stderr.close()
            stdout.close()
            c.close()
        except: pass
        
        return checkerlib.CheckResult.OK

    @trywrapper
    def check_service(self):
        # TODO: Implement (maybe use `utils.generate_message()`
        try:
            if run_testcase(self.ip, "1", "FAUST_AAAFOQPjKnQ0MIUAAAAAd4RWiQ9426DI"):
                return checkerlib.CheckResult.OK
            return checkerlib.CheckResult.FAULTY
        except Down:
            return checkerlib.CheckResult.DOWN
        except Faulty:
            return checkerlib.CheckResult.FAULTY

    @trywrapper
    def check_flag(self, tick):
        # TODO: Implement
        try:
            c = state_connection(self.ip, str(tick))
        except paramiko.ssh_exception.AuthenticationException:
            return checkerlib.CheckResult.FLAG_NOT_FOUND
        except Faulty:
            return checkerlib.CheckResult.FAULTY
        except paramiko.ssh_exception.SSHException:
            return checkerlib.CheckResult.DOWN
        except Down:
            return checkerlib.CheckResult.DOWN
        stdin, stdout, stderr = c.exec_command("/opt/bin/ghshow")
        stdin.close()
        answer = stdout.read()
        try:
            stdout.close()
            stderr.close()
            c.close()
        except: pass
        f = checkerlib.get_flag(tick).encode()
        logging.info("searching for flag %s" % f)
        logging.info("answer in check_flag: %s" %answer)
        if f in answer:
            logging.info("found")
            return checkerlib.CheckResult.OK
        else:
            logging.info("not found")
            return checkerlib.CheckResult.FLAG_NOT_FOUND

if __name__ == '__main__':

    checkerlib.run_check(Checker)

