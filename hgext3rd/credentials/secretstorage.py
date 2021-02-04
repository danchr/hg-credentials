# secretstorage.py — store passwords using the Secret Service API
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

import contextlib

from mercurial.pycompat import sysbytes, sysstr, strurl

import secretstorage


@contextlib.contextmanager
def secret_connection():
    with contextlib.closing(secretstorage.dbus_init()) as conn:
        yield conn


def get_attrs(ui, urlobj):
    attrs = {
        "application": "Mercurial",
        "host": strurl(urlobj.host),
        "path": strurl(urlobj.path),
        "scheme": strurl(urlobj.scheme),
    }

    if urlobj.user:
        attrs["user"] = strurl(urlobj.user)

    if urlobj.port:
        attrs["port"] = int(sysstr(urlobj.port))

    if urlobj.realm:
        attrs["realm"] = strurl(urlobj.realm)

    return attrs


def save_password(ui, urlobj):
    attrs = get_attrs(ui, urlobj)

    if ui.debugflag:
        ui.debug(b"saving to secret storage: %s\n" % sysbytes(repr(attrs)))

    with secret_connection() as conn:
        coll = secretstorage.collection.get_any_collection(conn)

        item = coll.create_item(
            "Mercurial (%s)" % sysstr(urlobj.authinfo()[0]),
            attrs,
            urlobj.passwd,
            True,
        )
        # item.set_label("Mercurial (%s)" % sysstr(urlobj.authinfo()[0]))


def find_password(ui, urlobj):
    attrs = get_attrs(ui, urlobj)

    if ui.debugflag:
        ui.debug(b"querying secret storage: %s\n" % sysbytes(repr(attrs)))

    with secret_connection() as conn:
        for item in secretstorage.search_items(conn, attrs):
            itemattrs = item.get_attributes()

            return itemattrs.get("user", ""), sysstr(item.get_secret())
        else:
            ui.debug(b"nothing found\n")

    return None, None
