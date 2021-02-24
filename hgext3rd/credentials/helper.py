# helper.py — use git-compatible helpers for password storage
#
# Copyright © 2021, Dan Villiom Podlaski Christiansen
#
# This software may be used and distributed according to the terms of
# the GNU General Public License version 2 or any later version.
#

import contextlib

from mercurial import encoding
from mercurial.pycompat import sysbytes, sysstr, strurl
from mercurial.utils import procutil


def save_password(ui, urlobj):
    helper = ui.config(b"credentials", b"helper")

    if not helper:
        raise ValueError("no helper available")

    attrs = {
        b"protocol": urlobj.scheme,
        b"host": (
            b":".join((urlobj.host, urlobj.port))
            if urlobj.port
            else urlobj.host
        ),
        b"path": urlobj.path,
        b"username": encoding.strtolocal(urlobj.user),
        b"password": encoding.strtolocal(urlobj.passwd),
    }

    req = b"".join(b"%s=%s\n" % e for e in attrs.items())

    procutil.pipefilter(req, b"%s store" % helper)


def find_password(ui, urlobj):
    helper = ui.config(b"credentials", b"helper")

    if not helper:
        return None, None

    attrs = {
        b"protocol": urlobj.scheme,
        b"host": (
            b":".join((urlobj.host, urlobj.port))
            if urlobj.port
            else urlobj.host
        ),
    }

    if urlobj.user:
        attrs[b"username"] = urlobj.user

    if urlobj.path:
        attrs[b"path"] = urlobj.path

    req = b"".join(b"%s=%s\n" % (k, v) for k, v in attrs.items())

    resp = procutil.pipefilter(req, b"%s get" % helper)

    attrs = dict(line.split(b"=", 1) for line in resp.splitlines())

    return attrs.get(b"username"), attrs.get(b"password")
