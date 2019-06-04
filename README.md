# Pulautin

Pulautin is a music collection management tool.

It's run on command line and written in Python.

Status: WIP

## What can it do

Let's assume you have a large collection of music arranged in well defined
directory structure like A/Artist/Album/Track01.flac

Pulautin automates or at least tries to help with these:

### Scan the library for fast access

This is not really a feature, but before doing anything Pulautin
scans the collection into a sqlite database, so using it interactively
will be super fast. It can update the database when files change.

### Find duplicates

Pulautin tries to find duplicate directories and you can choose
which one to keep and which one to delete. Files are checked
for their md5 sums and all files must be in both directories.

### Import music to library

A friend gives you a large USB stick with lot of good non-copyrighted music.

You want to import it to your collection while preserving your nice
directory structure and skip duplicates.

Manually this would take ages. Pulautin tries to automate this as
much as possible.

* Albums (by one artist) can moved automatically to correct place in directory structure.
* Various artists (album with many artists) can be moved to a defined directory
* Soundtracks (Usually have OST or so in their name)  can be moved to a defined directory
* Directories without tags or otherwise unidentifiable can be moved to a defined directory for manual import
* Any other logic can be implemented, it's just Python
