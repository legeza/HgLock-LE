# HgLock-LE
# hglock.py - file locking mechanizm for Mercurial
#
# Version 0.1
#
# Copyright 2012 Vladimir Legeza <vladimir.legeza@gmail.com>
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

import sys
import os
import re
from mercurial import hg
from mercurial import cmdutil
from mercurial import util
from mercurial import i18n
from mercurial import store

import datetime
# Dict fields id's mapping:
# Dict example:    "FileName=(UserName,LockDate)"
UserName=0
LockDate=1

# Set OS dependant delimiters
newLine=os.linesep  # '\n' - for unix
pathSep=os.path.sep # '/' - for unix




def LoadData(lockFile):
  "Load data from file"
  encodefilename, decodefilename = store._buildencodefun()
  lockedFilesList = dict()
  if os.path.exists(lockFile):
    for line in open(lockFile):
      line = line.strip()
      file,user,date=line.split(":",2)
      file = decodefilename(file)
      lockedFilesList[file] = (user,date)
  return lockedFilesList
 



def StoreData(lockFile, lockedFilesList):
  "Store locking information into the file"
  encodefilename, decodefilename = store._buildencodefun()
  outputF = open(lockFile,"w")
  os.chmod(lockFile, 0664)

  for file in lockedFilesList.keys():
    outputF.write(encodefilename(file) + ":" + ":".join(lockedFilesList[file]) + newLine)
  outputF.close()




def lock(ui, repo, *pats, **opts):
  """
  HGLock-LE is the extansion implements file locking funcionality that is vary similar to rcs(1).

  Usage:
         $ hg lock [-v] <file ...>
               If no file specified, the list of already locked files and
               lock owners will displayed.
         -v    Will display a bit more information then usual.
  """
  lockFile = repo.root + pathSep + ".hg" + pathSep + "locked.files"
  user = ui.username()
  ui.note("repository: %s\n" % repo.root)
  ui.note("lockfile: %s\n" % lockFile)
  ui.note("user name: %s\n\n" % user)

  # Identify whether function is called as a hook,
  # and if so, get the list of files to be proceed.
  if 'hooktype' in opts:
    pats = opts['args'].split()
    # Remove commands and options
    for unit in pats[::-1]:
      if unit not in repo.dirstate:
	    pats.remove(unit)

  # Calculate file path in repository
  filesList=list()
  err=0
  for file in pats:
    m = re.match(repo.root + pathSep + "(.+)",os.path.abspath(os.getcwd() + pathSep + file))
    if m.groups()[0] in repo.dirstate:
      filesList.append(m.groups()[0])
    else:
      ui.warn("%s\n" % (file))
      err += 1
  if err:
    raise util.Abort(i18n._("cant't lock untracked file(s)."))

  # Load stored locking data
  lockedFilesList = LoadData(lockFile)
  
  # Show available locks if "filesList" is empty
  if not filesList:
    for file in lockedFilesList.keys():
      if ui.verbose:
        ui.write("%s is locked by %s (%s)\n" % \
         (file, lockedFilesList[file][UserName], lockedFilesList[file][LockDate]))
      else:
    	ui.write("%s (%s)\n" % (file, lockedFilesList[file][UserName]))
    return 0

  # Collect locked files if available
  alreadyLocked = list()
  for file in filesList:
    if file in lockedFilesList:
      alreadyLocked.append(file)

  if not alreadyLocked:
    # Locking
    for file in filesList:
      localTime = datetime.datetime.now()
      localTime = localTime.ctime()
      lockedFilesList[file] = (user,localTime)
      ui.note("locking: %s\n" % file)
      #ui.write ("%s is locked.\n" % (file))
    StoreData(lockFile, lockedFilesList)
  else:
    # Exit with errno
    for file in alreadyLocked:
      if ui.verbose:
        ui.write("%s - is already locked by %s (%s)\n" % \
         (file,lockedFilesList[file][UserName],lockedFilesList[file][LockDate]))
      else:
        ui.write("%s (%s)\n" % \
         (file,lockedFilesList[file][UserName]))
    raise util.Abort(i18n._("lock(s) conflict."))



  
def unlock(ui, repo, *pats, **opts):
  """
  Release Lock:
          $ hg unlock [-f] [-v] <file ...>
                If no file specified, unlock would try to relaes all availble
                locks.
          -f    Force unlock. Allows you to break others locks. Owner will
                be notified about this.
          -v    Will display a bit more information then usual.
  """
  lockFile = repo.root + pathSep + ".hg" + pathSep + "locked.files"
  user = ui.username()
  ui.note("repository: %s\n" % repo.root)
  ui.note("lockfile: %s\n" % lockFile)
  ui.note("user name: %s\n\n" % user)

  # Identify whether function is called as a hook,
  # and if so, get the list of files to be proceed.
  if 'hooktype' in opts:
    pats = opts['args'].split()
    # Remove commands and options
    for unit in pats[::-1]:
      if unit not in repo.dirstate:
	    pats.remove(unit)

  # If files are not specified
  # and functil was called as a hook
  if not pats and 'hooktype' in opts:
    # States : modified, added, removed, deleted, unknown, ignored, clean"
    # Get files related to the first four statuses.
    pats = list()
    for status in repo.status()[:4]:
      pats += status

  # Load stored locking data
  lockedFilesList = LoadData(lockFile)

  # If files are not specified
  # try to release all available locks
  if not pats and 'hooktype' not in opts:
   pats = lockedFilesList.keys()

  #Calculate file path in repository
  filesList=list()
  for file in pats:
    m = re.match(repo.root + pathSep + "(.+)",os.path.abspath(os.getcwd() + pathSep + file))
    filesList.append(m.groups()[0])

  err = 0 
  for file in filesList:
    if file in lockedFilesList:
      # UnLock
      if not lockedFilesList[file][UserName] == user:
	    # Force unlock and send email to lock owner
        if opts['force']:
          # Email format: RFC 2822
          # example: "Vladimir Legeza <vladimir.legeza@gmail.com>"
          from mercurial import mail
          sendFrom = util.email(user)
          sendTo = [util.email(lockedFilesList[file][UserName])]
          message = "The lock you have set on '%s' file was removed by %s." % \
		   (file, lockedFilesList[file][UserName])
          ui.note("sending email to: %s\n" % sendTo)
          mail.sendmail(ui, sendFrom, sendTo, message)
          ui.note("unlocking: %s\n" % file)
          lockedFilesList.pop(file)
        else:
          err += 1
          ui.warn("%s - locked by %s.\n" % (file, lockedFilesList[file][UserName]))
      else:
        ui.note("unlocking: %s\n" % file)
        lockedFilesList.pop(file)
  if err:
    raise util.Abort(i18n._("Lock ownership violation."))

  # Save changes 
  StoreData(lockFile, lockedFilesList)


    
# COMMANDS
cmdtable = {
  "lock": (lock, [], "[-v] file..."),
  "unlock": (unlock, [
       ('f', 'force', None, "Unlock even you are not owner."),
       ], "[-v] [-f] file..."),
}

# HOOKS
def uisetup(ui):
  ui.setconfig("hooks", "post-add.hglock", lock)
  ui.setconfig("hooks", "pre-commit.hglock", unlock)

