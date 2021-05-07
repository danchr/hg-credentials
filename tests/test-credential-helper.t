Test the extension with Git's credential helper

  $ cat >> $HOME/.gitconfig <<EOF
  > EOF

  $ cat >> $HGRCPATH <<EOF
  > [extensions]
  > hg-credentials = $TESTDIR/../hgext3rd/credentials
  > getpass = $TESTTMP/get_pass.py
  > auth = $RUNTESTDIR/httpserverauth.py
  > EOF

Allow password prompts without a TTY:

  $ cat << EOF > get_pass.py
  > from __future__ import generator_stop
  > import getpass, os, sys
  > def newgetpass(args):
  >     passwd = input(*args)
  >     print(passwd, file=sys.stderr)
  >     return passwd
  > getpass.getpass = newgetpass
  > EOF

  $ hg init repo
  $ cd repo
  $ hg serve -p $HGPORT -d --pid-file=$DAEMON_PIDS
  $ cd ..

  $ hg clone http://localhost:$HGPORT clone
  abort: http authorization required for http://localhost:$HGPORT/
  [255]

  $ cat >> $HGRCPATH <<EOF
  > [ui]
  > interactive = yes
  > promptecho = yes
  > EOF

  $ ( echo user; echo password; yes ) | \
  > hg clone http://localhost:$HGPORT clone || true
  http authorization required for http://localhost:$HGPORT/
  realm: mercurial
  user: user
  password: password
  would you like to save this password? (Y/n)  y
  warning: failed to access credentials using the Helper
  abort: HTTP Error 403: no

  $ cat >> $HGRCPATH <<EOF
  > [credentials]
  > helper= git credential-store
  > EOF

  $ ( echo pass; yes ) | \
  > hg clone http://user@localhost:$HGPORT clone
  http authorization required for http://localhost:$HGPORT/
  realm: mercurial
  user: user
  password: pass
  would you like to save this password? (Y/n)  y
  no changes found
  updating to branch default
  0 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ hg -R clone pull
  pulling from http://user@localhost:$HGPORT/
  no changes found

  $ cat $TESTTMP/.git-credentials | sed s/%3a/:/
  http://user:pass@localhost:$HGPORT/

  $ cat > $TESTTMP/.git-credentials <<EOF
  > http://user:notpass@localhost%3a\$HGRPORT/
  > EOF

  $ ( echo pass; yes ) | \
  > hg pull -R clone http://user@localhost:$HGPORT
  pulling from http://user@localhost:$HGPORT/
  http authorization required for http://localhost:$HGPORT/
  realm: mercurial
  user: user
  password: pass
  would you like to save this password? (Y/n)  y
  no changes found
  $ hg -R clone pull
  pulling from http://user@localhost:$HGPORT/
  no changes found

this is kind of buggy, as we should have called reject

  $ cat $TESTTMP/.git-credentials | sed s/%3a/:/
  http://user:pass@localhost:$HGPORT/
  http://user:notpass@localhost:$HGRPORT/
