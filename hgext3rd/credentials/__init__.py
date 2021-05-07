# credentials — store Mercurial passwords securely
#
# Copyright © 2021, Dan Villiom Podlaski Christiansen
#
# This software may be used and distributed according to the terms of
# the GNU General Public License version 2 or any later version.
#
"""store passwords securely

This extension offers no commands and no configuration. Once enabled,
you get a prompt offering to save any HTTP passwords entered. Once a
password is saved, there's nothing more to do. You'll get a new
prompt, should the password suddenly stop working. To manage or delete
your passwords, use the relevant application included with
OS to edit the password items labeled ``Mercurial
($USER@$HOSTNAME)``.

If you have many passwords on the same server, such as on a hosting
service, you can avoid entering passwords for each and every one by
using the ``auth`` configuration section::

  [auth]
  example.prefix = example.com
  example.username = me

This will cause all repositories on ``https://example.com`` to share
the same storage item. See :hg:`help config.auth` for details.

"""

import contextlib
import os
import sys

from mercurial import demandimport
from mercurial import extensions
from mercurial import httpconnection
from mercurial import pycompat
from mercurial import registrar
from mercurial import url
from mercurial import util

try:
    from mercurial.utils import urlutil
except ImportError:
    from mercurial import util as urlutil


testedwith = b"5.6 5.7 5.8"
minimumhgversion = b"5.6"
buglink = b"https://foss.heptapod.net/mercurial/hg-credentials/issues"

__version__ = '0.1.1'

cmdtable = {}
command = registrar.command(cmdtable)

configtable = {}
configitem = registrar.configitem(configtable)

configitem(
    b"credentials",
    b"helper",
    default=None,
)


def get_backends(ui):
    if sys.platform == "darwin":
        try:
            from . import keychain as backend

            yield b"Keychain", backend
        except ImportError:
            ui.traceback()

    if os.name == "posix":
        try:
            from . import secretstorage as backend

            yield b"Secret Service", backend
        except ImportError:
            ui.traceback()

    # the simple fallback
    from . import helper as backend

    yield b"Helper", backend


@contextlib.contextmanager
def backend_handler(ui, name):
    try:
        yield
    except (ImportError, AttributeError):
        if ui.debugflag:
            ui.traceback()
            ui.debug(b"credentials backend %s not available\n" % name)
    except Exception as e:
        ui.traceback()
        ui.warn(b"warning: failed to access credentials using the %s\n" % name)


def get_auth_url(ui, uris, user=None, realm=None):
    if isinstance(uris, tuple):
        uri = uris[0]
    else:
        uri = uris

    urlobj = urlutil.url(pycompat.bytesurl(uri))
    urlobj.query = urlobj.fragment = None

    bestauth = httpconnection.readauthforuri(
        ui, pycompat.bytesurl(uri), pycompat.bytesurl(user)
    )

    if bestauth is not None:
        group, auth = bestauth

        prefix = auth[b"prefix"]

        if b"://" in prefix:
            prefix = prefix.split(b"://", 1)[1]

        if b"/" in prefix:
            urlobj.host, urlobj.path = prefix.split(b"/", 1)
        else:
            urlobj.host, urlobj.path = prefix, b""

    if user is not None:
        urlobj.user = pycompat.bytesurl(user)

    if realm is not None:
        urlobj.realm = realm

    return urlobj


def add_password(orig, self, realm, uris, user, passwd):
    if orig is not None:
        orig(self, realm, uris, user, passwd)

    if not passwd:
        return

    urlobj = get_auth_url(self.ui, uris, user, realm)

    if not self.ui.interactive() or self.ui.promptchoice(
        b"would you like to save this password? (Y/n) $$ &Yes $$ &No"
    ):
        return

    urlobj.user = user
    urlobj.passwd = passwd

    for name, backend in get_backends(self.ui):
        with backend_handler(self.ui, name):
            backend.save_password(self.ui, urlobj)
            break


def find_user_password(orig, self, realm, uri):
    try:
        seen = self._seen
    except AttributeError:
        seen = self._seen = set()

    # only ever search the storage once as the password might be
    # wrong, and that should trigger a prompt
    if (realm, uri) not in seen:
        seen.add((realm, uri))

        urlobj = get_auth_url(self.ui, uri, realm=realm)

        for name, backend in get_backends(self.ui):
            with backend_handler(self.ui, name):
                user, passwd = backend.find_password(self.ui, urlobj)

                if passwd is not None:
                    return user, passwd

    # trigger a prompt
    user, passwd = orig(self, realm, uri)

    # it'd be nice to only store passwords once we know that they
    # work, but mercurial doesn't really expose that notion
    add_password(None, self, realm, uri, user, passwd)

    return user, passwd


@command(
    b"debugcredentialbackends",
    (),
    optionalrepo=True,
    intents={b"readonly"},
)
def debugcredentialbackends(ui, repo):
    """check status of available backends"""

    for name, backend in get_backends(ui):
        try:
            backend.find_password
            backend.save_password
            ui.write(b"ok: %s\n" % name)
        except (ImportError, AttributeError) as e:
            ui.traceback()
            ui.write(b"not ok: %s\n" % name)


def uisetup(ui):
    cls = url.passwordmgr

    # wrap the methods individually, so that we also affect other
    # existing ui instances
    extensions.wrapfunction(cls, "find_user_password", find_user_password)
    extensions.wrapfunction(cls, "add_password", add_password)
