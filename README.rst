=====================
Credentials Extension
=====================

This is an extension for Mercurial 5.6 or later, allowing you to store
HTTP passwords securely. The extension itself does not offer any
commands, you simply enable it, and get an extra prompt::

  $ hg pull
  pulling from https://example.com/private/repo
  http authorization required for https://example.com/private/repo
  realm: Mercurial
  user: me
  password: <SECRET>
  would you like to save this password? (Y/n)  y
  searching for changes
  no changes found

That would result an a new item named in your key chain or key ring::

  Mercurial (me@example.com)

Once a password is saved, there's nothing more to do. You'll get a new
prompt, should the password suddenly stop working. To manage or delete
your passwords, use the *Keychain Services* application included with
macOS, GNOME Keyring or something similar included in your desktop
environment.

Requirements
------------

* Python 3.6 or later.
* Mercurial 5.6 or later.
* `SecretStorage <https://secretstorage.readthedocs.io/>`_ on
  platforms other than macOS.

Windows is not supported, yet.

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

Alternatives
------------

The most obvious alternative to this extension is the `Mercurial
Keyring <https://pypi.org/project/mercurial_keyring/>`_ extension. It
supports older versions of Mercurial and more backends, but saves
passwords in a less readable fashion.

Future plans
------------

* Consider whether it makes sense to implement a completely custom
  ``urllib2`` password manager, so passwords aren't stored in memory
  any longer than strictly necessary.

Acknowledgements
----------------

Thanks you to Octobus and Heptapod for hosting this project, and for
making Mercurial development fun again!
