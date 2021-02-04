# keychain.py — store Mercurial passwords in the macOS keychain
#
# Copyright © 2021, Dan Villiom Podlaski Christiansen
#
# This software may be used and distributed according to the terms of
# the GNU General Public License version 2 or any later version.
#
"""store passwords in the macOS keychain

This extension offers no commands and no configuration. Once enabled,
you get a prompt offering to save any HTTP passwords entered. Once a
password is saved, there's nothing more to do. You'll get a new
prompt, should the password suddenly stop working. To manage or delete
your passwords, use the “Keychain Services” application included with
macOS to edit the password items labeled ``Mercurial
($USER@$HOSTNAME)``.

If you have many passwords on the same server, such as on a hosting
service, you can avoid entering passwords for each and every one by
using the ``auth`` configuration section::

  [auth]
  example.prefix = example.com
  example.username = me

This will cause all repositories on ``https://example.com`` to share
the same Keychain item. See :hg:`help config.auth` for details.

"""

from mercurial import demandimport
from mercurial import extensions
from mercurial import httpconnection
from mercurial import pycompat
from mercurial import url
from mercurial import util


testedwith = b"5.6 5.7"
minimumhgversion = b"5.6"
buglink = b"https://foss.heptapod.net/mercurial/hg-keychain/issues"

# pyobjc uses lazy modules internally, so suppress demandimport for
# them, but don't import them yet, as that's relatively slow --
# fortunately for us, accessing a repository over the network is even
# slower, so no-one will notice the slowness of repeated imports
demandimport.IGNORES |= {
    "CoreFoundation",
    "Foundation",
    "Security",
}

Security = None


def _import_security():
    global Security
    if Security is None:
        Security = __import__("Security")


def _get_auth_url(ui, uris, user=None):
    if isinstance(uris, tuple):
        uri = uris[0]
    else:
        uri = uris

    urlobj = util.url(pycompat.bytesurl(uri))
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

    if urlobj.scheme == b"http":
        protocol = Security.kSecProtocolTypeHTTP
    elif urlobj.scheme == b"https":
        protocol = Security.kSecProtocolTypeHTTPS
    else:
        raise ValueError(pycompat.sysstr(urlobj.scheme))

    urlobj.protocol = protocol.to_bytes(4, "big")

    return urlobj


def _get_keychain_error(err):
    import Security

    msg = Security.SecCopyErrorMessageString(err, None)

    return pycompat.sysbytes(msg[0].lower() + msg[1:])


def _get_keychain_query(ui, uri, user=None, realm=None, with_data=True):
    import Security

    urlobj = _get_auth_url(ui, uri, user)

    query = {
        Security.kSecClass: Security.kSecClassInternetPassword,
        Security.kSecAttrServer: pycompat.strurl(urlobj.host),
        Security.kSecAttrPath: pycompat.strurl(urlobj.path),
        Security.kSecAttrProtocol: pycompat.strurl(urlobj.protocol),
        Security.kSecMatchLimit: Security.kSecMatchLimitOne,
        Security.kSecReturnAttributes: with_data,
        Security.kSecReturnData: with_data,
    }

    if urlobj.user is not None:
        query[Security.kSecAttrAccount] = pycompat.strurl(urlobj.user)

    if urlobj.port:
        query[Security.kSecAttrPort] = int(pycompat.sysstr(urlobj.port))

    if realm is not None:
        query[Security.kSecAttrSecurityDomain] = realm

    if ui.debugflag:
        ui.debug(b"querying keychain: %s\n" % pycompat.sysbytes(repr(query)))

    return query


def _find_keychain_item(ui, uri, realm, user=None):
    query = _get_keychain_query(ui, uri, user, realm)

    err, ref = Security.SecItemCopyMatching(query, None)
    if not err:
        return ref

    else:
        ui.debug(
            b"keychain search failed: %s (%d)\n"
            % (_get_keychain_error(err), err),
        )

        return None


def add_password(orig, self, realm, uris, user, passwd):
    if orig is not None:
        orig(self, realm, uris, user, passwd)

    if not passwd:
        return

    _import_security()

    urlobj = _get_auth_url(self.ui, uris, pycompat.bytesurl(user))

    item = _find_keychain_item(self.ui, uris, realm, user)

    if item and item[Security.kSecValueData] == passwd:
        return

    if not self.ui.interactive() or self.ui.promptchoice(
        b"would you like to save this password? (Y/n) $$ &Yes $$ &No"
    ):
        return

    query = _get_keychain_query(self.ui, uris, user, realm, with_data=False)

    attrs = {
        Security.kSecClass: Security.kSecClassInternetPassword,
        Security.kSecAttrLabel: "Mercurial (%s@%s)"
        % (
            pycompat.strurl(user),
            pycompat.strurl(urlobj.host),
        ),
        Security.kSecAttrAccount: pycompat.strurl(user),
        Security.kSecValueData: pycompat.sysbytes(passwd),
        Security.kSecAttrServer: pycompat.strurl(urlobj.host),
        Security.kSecAttrPath: pycompat.strurl(urlobj.path),
        Security.kSecAttrSecurityDomain: pycompat.sysstr(realm),
        Security.kSecAttrPort: int(pycompat.sysstr(urlobj.port)),
        Security.kSecAttrProtocol: pycompat.strurl(urlobj.protocol),
    }

    if self.ui.debugflag:
        safeattrs = attrs.copy()
        safeattrs[Security.kSecValueData] = b"***"

        self.ui.debug(
            b"saving to keychain: %s\n" % pycompat.sysbytes(repr(safeattrs))
        )

    err = Security.SecItemUpdate(
        query,
        attrs,
    )

    if err:
        self.ui.debug(
            b"adding new keychain item due to %s (%d)\n"
            % (_get_keychain_error(err), err)
        )

        err = Security.SecItemAdd(attrs, None)[0]

    if err:
        self.ui.warn(
            b"warning: password was not saved in the keychain as %s (%d)\n"
            % (_get_keychain_error(err), err),
        )


def find_user_password(orig, self, realm, uri):
    try:
        seen = self._seen
    except AttributeError:
        seen = self._seen = set()

    # only ever search the keychain once as the password might be
    # wrong, and this is a re-prompt
    if (realm, uri) not in seen:
        seen.add((realm, uri))

        _import_security()

        item = _find_keychain_item(self.ui, uri, realm)

        if item:

            date = pycompat.sysbytes(
                str(item[Security.kSecAttrModificationDate])
            )

            label = pycompat.sysbytes(str(item[Security.kSecAttrLabel]))

            self.ui.debug(
                b"using keychain item '%s' modified on %s\n" % (label, date),
            )

            user = item[Security.kSecAttrAccount]
            passwd = pycompat.sysstr(bytes(item[Security.kSecValueData]))

            return user, passwd

    user, passwd = orig(self, realm, uri)

    # it'd be nice to only store passwords once we know that they
    # work, but mercurial doesn't really expose that notion
    add_password(None, self, realm, uri, user, passwd)

    return user, passwd


def uisetup(ui):
    cls = url.passwordmgr

    extensions.wrapfunction(cls, "find_user_password", find_user_password)
    extensions.wrapfunction(cls, "add_password", add_password)
