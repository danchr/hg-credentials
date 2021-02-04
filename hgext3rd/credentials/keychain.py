# keychain.py — store passwords in the macOS keychain
#
# Copyright © 2021, Dan Villiom Podlaski Christiansen
#
# This software may be used and distributed according to the terms of
# the GNU General Public License version 2 or any later version.
#
# Alternatively, you may use this file under the following terms:
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#

from mercurial.pycompat import sysbytes, sysstr, strurl

import Security


def _get_keychain_error(err):
    msg = Security.SecCopyErrorMessageString(err, None)

    return sysbytes(msg[0].lower() + msg[1:])


def get_protocol(urlobj):
    if urlobj.scheme == b"http":
        protocol = Security.kSecProtocolTypeHTTP
    elif urlobj.scheme == b"https":
        protocol = Security.kSecProtocolTypeHTTPS
    else:
        raise ValueError(sysstr(urlobj.scheme))

    return protocol.to_bytes(4, "big")


def _get_keychain_query(ui, urlobj, with_data=True):
    query = {
        Security.kSecClass: Security.kSecClassInternetPassword,
        Security.kSecAttrServer: strurl(urlobj.host),
        Security.kSecAttrPath: strurl(urlobj.path),
        Security.kSecAttrProtocol: strurl(get_protocol(urlobj)),
        Security.kSecMatchLimit: Security.kSecMatchLimitOne,
        Security.kSecReturnAttributes: with_data,
        Security.kSecReturnData: with_data,
    }

    if urlobj.user:
        query[Security.kSecAttrAccount] = strurl(urlobj.user)

    if urlobj.port:
        query[Security.kSecAttrPort] = int(sysstr(urlobj.port))

    if urlobj.realm:
        query[Security.kSecAttrSecurityDomain] = strurl(urlobj.realm)

    if ui.debugflag:
        ui.debug(b"querying keychain: %s\n" % sysbytes(repr(query)))

    return query


def save_password(ui, urlobj):
    query = _get_keychain_query(ui, urlobj, with_data=False)

    attrs = {
        Security.kSecClass: Security.kSecClassInternetPassword,
        Security.kSecAttrLabel: "Mercurial (%s@%s)"
        % (
            strurl(urlobj.user),
            strurl(urlobj.host),
        ),
        Security.kSecAttrAccount: strurl(urlobj.user),
        Security.kSecValueData: sysbytes(urlobj.passwd),
        Security.kSecAttrServer: strurl(urlobj.host),
        Security.kSecAttrPath: strurl(urlobj.path),
        Security.kSecAttrSecurityDomain: sysstr(urlobj.realm),
        Security.kSecAttrPort: int(sysstr(urlobj.port or b"0")),
        Security.kSecAttrProtocol: strurl(get_protocol(urlobj)),
    }

    if ui.debugflag:
        safeattrs = attrs.copy()
        safeattrs[Security.kSecValueData] = b"***"

        ui.debug(b"saving to keychain: %s\n" % sysbytes(repr(safeattrs)))

    ui.debug(b"trying to update keychain\n")

    err = Security.SecItemUpdate(
        query,
        attrs,
    )

    if err:
        ui.debug(
            b"adding new keychain item due to %s (%d)\n"
            % (_get_keychain_error(err), err)
        )

        err = Security.SecItemAdd(attrs, None)[0]

    if err:
        ui.warn(
            b"warning: password was not saved in the keychain as %s (%d)\n"
            % (_get_keychain_error(err), err),
        )


def find_password(ui, urlobj):
    query = _get_keychain_query(ui, urlobj)

    err, item = Security.SecItemCopyMatching(query, None)
    if err:
        ui.debug(
            b"keychain search failed: %s (%d)\n"
            % (_get_keychain_error(err), err),
        )
        return None, None

    date = sysbytes(str(item[Security.kSecAttrModificationDate]))

    label = sysbytes(str(item[Security.kSecAttrLabel]))

    ui.debug(
        b"using keychain item '%s' modified on %s\n" % (label, date),
    )

    user = item[Security.kSecAttrAccount]
    passwd = sysstr(bytes(item[Security.kSecValueData]))

    return user, passwd
