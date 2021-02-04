=====================
Credentials Extension
=====================

This is an extension for Mercurial 5.7 or later, allowing you to store
HTTP passwords securely in the macOS Keychain. The extension itself
does not offer any commands: You simply enable it, and get an extra
prompt::

  $ hg pull
  pulling from https://example.com/private/repo
  http authorization required for https://example.com/private/repo
  realm: Mercurial
  user: me
  password: <SECRET>
  would you like to save this password? (Y/n)  y
  searching for changes
  no changes found

That would result an a new Keychain item named::

  Mercurial (me@example.com)

Once a password is saved, there's nothing more to do. You'll get a new
prompt, should the password suddenly stop working. To manage or delete
your passwords, use the *Keychain Services* application included with
macOS.

Requirements
------------

* Python 3.6 or later.
* Mercurial 5.7 or later.
* `PyObjC <https://pyobjc.readthedocs.io/>`_ on macOS.

Windows is not supported.

Installation and usage
----------------------

Install the extension and its dependencies with Pip::

  $ pip install .

Then, add the following lines to your ``~/.hgrc``::

  [extensions]
  credentials =

To avoid entering passwords for each and every repository, use
``auth.schemes``::

  [auth]
  example.prefix = example.com
  example.username = me

This will cause all repositories on ``https://example.com`` to resolve
to the same Keychain item. See ``hg help config.auth`` for details.

Future plans
------------

* Add support for Gnome Keychain.
* Add support for Git credential helpers.
* Consider whether it makes sense to implement a completely custom
  ``urllib2`` password manager, so passwords aren't stored in memory
  any longer than strictly necessary.
