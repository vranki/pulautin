#! /usr/bin/env python2
# -*- encoding: "utf-8"


# select md5,dirname,filename from files,directories WHERE files.directory=directories.id AND md5 IS NOT NULL ORDER BY md5,directory;

import os
import sys
import sqlite3
import argparse
import hashlib

parser = argparse.ArgumentParser(description='Pulautin')
parser.add_argument('operation', help="Operation: scan | finddupes (default)", nargs='?', default='finddupes')
parser.add_argument('--dir', help="Directory to scan")
args = parser.parse_args()


conn = sqlite3.connect('pulautin.db')
conn.execute('pragma foreign_keys=ON')
c = conn.cursor()

def finddupes():
    c.execute('''SELECT a.*,dirname FROM files a 
    JOIN(SELECT filename,size,directory,COUNT(*) FROM files GROUP BY size HAVING COUNT(*) > 1) 
    b ON a.size == b.size INNER JOIN directories ON a.directory==directories.id WHERE a.size > 0 ORDER BY filename''')
    potentials = []
    while True:
        row = c.fetchone()
        if(not row):
            break
        fullfilename = os.path.join(row[5],row[1])
        potentials.append( [row[0], row[1], row[5]] )

    for pot in potentials:
        filename = pot[1]
        path = pot[2]
        directoryid = pot[0]
        fullfilename = os.path.join(pot[2],pot[1])
        filedata = get_file_data(directoryid, filename)
        if not filedata[2]:
            md5 = get_md5(fullfilename)
            c.execute('''UPDATE files SET md5=? WHERE (filename==? AND directory=?)''', [md5, filename, directoryid])

    conn.commit()

    c.execute('''SELECT * FROM duplicates ORDER BY md5''')
    dupes = []
    dupegroup = {}
    while True:
        row = c.fetchone()
        if(not row):
            if len(dupegroup) > 0:
                dupes.append(dupegroup)
            break
        md5 = row[4]
        if len(dupegroup) == 0:
            dupegroup['md5'] = md5
            dupegroup['files'] = []
        if md5 == dupegroup['md5']:
            dupegroup['files'].append( os.path.join(row[5], row[1]) )
        else:
            dupes.append(dupegroup)
            dupegroup = {}
            dupegroup['md5'] = md5
            dupegroup['files'] = [os.path.join(row[5], row[1])]

    for group in dupes:
        print("DUPE group: ", group['md5'])
        print(group['files'])


    c.execute('''SELECT DISTINCT directory FROM duplicates ORDER BY directory''')

    dirs = []

    while True:
        dirdata = []
        row = c.fetchone()
        if not row:
            break
        dirs.append(row[0])

    for dir in dirs:
        dirdata = get_directory_data(dir)
        print("Examining dir " + dirdata[0])
        c.execute("SELECT filename,md5 from files WHERE directory=?", [dir])
        files = []
        while True:
            row = c.fetchone()
            if not row:
                break
            files.append(row)

        alldupes = True
        for file in files:
            print("Checking file ", file)
            if not file_has_dupe(file):
                alldupes = False
        
        if alldupes:
            print("All files in dir " + dirdata[0] + " are dupes!")

def file_has_dupe(file):
    c.execute('select count(*) from files where filename==? and md5==?', [file[0], file[1]])
    row = c.fetchone()
    return row[0] > 1

def get_md5(fname):
    hash_md5 = hashlib.md5()
    try:
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
    except IOError, e:
        print("Failed to calculate md5 for", fname, e)
    return hash_md5.hexdigest()

def convert_name(name):
    try:
        return name.decode('utf-8')
    except UnicodeDecodeError:
        ignored = unicode(name, errors='ignore')
        print("Warning: Can't decode name", name, " - using ", ignored)
        return ignored

def createTables():
    try:
        c.execute('''CREATE TABLE directories (id integer PRIMARY KEY, parent integer, dirname text, mtime integer)''')
        c.execute('''CREATE TABLE files (directory integer, filename text, size integer, mtime integer, md5 text, FOREIGN KEY(directory) REFERENCES directories(id));''')
        c.execute('''CREATE VIEW duplicates AS SELECT a.*,dirname FROM files a JOIN(SELECT md5, COUNT(*) FROM files GROUP BY md5 HAVING count(*)>1 ) b ON a.md5 = b.md5 INNER JOIN directories ON a.directory==directories.id''')
        conn.commit()
        print("Created tables")
    except sqlite3.OperationalError as err:
        print("Error creating tables: {0}".format(err))

def get_directory_data(id):
    c.execute("select dirname,mtime,id FROM directories WHERE id=?", [id])
    return c.fetchone()


def get_directory_id(dirname):
    c.execute("SELECT id FROM directories WHERE dirname==?", [convert_name(dirname)])
    row = c.fetchone()
    if row is not None:
        return row[0]
    return None

def get_file_data(directory, filename):
    c.execute("select filename,mtime,md5 FROM files WHERE filename=? AND directory=?", [filename, directory])
    return c.fetchone()

# Scans all files & dirs in the database and deletes the ones missing.
# TODO: Could be optimized by using mtimes.
def removeMissing():
    c.execute("select dirname, id FROM directories")
    while True:
        row = c.fetchone()
        if not row:
            break
        dirname = row[0]
        dirid = row[1]
        if not os.path.isdir(dirname):
            print('Dir', dirname, 'doesnt exist, removing from db..')
            c2 = conn.cursor()
            c2.execute('DELETE FROM files WHERE directory=?', [dirid])
            c2.execute('DELETE FROM directories WHERE id=?', [dirid])
            conn.commit()
            # Parent references should be gone now..

def scan():
    walk_dir = os.path.abspath(args.dir).encode('utf-8') 

    print('Scan root directory: ' + walk_dir + '...')

    for root, subdirs, files in os.walk(walk_dir):
        rootid = get_directory_id(root)
        parentid = get_directory_id(os.path.abspath(os.path.join(root, os.pardir)))
        mtime = os.path.getmtime(root)
        scan_files = False
        if not rootid:
            print(root + " previously unknown directory, adding to db..")
            c.execute("INSERT INTO directories(parent, dirname, mtime) VALUES (?, ?, ?)", [parentid, convert_name(root), mtime])
            conn.commit()
            scan_files = True

        rootid = get_directory_id(root)
        dirdata = get_directory_data(rootid)

        if dirdata[1] != mtime:
            print(root + "changed, scanning and updating it..")
            scan_files = True
            c.execute("UPDATE directories SET mtime=? WHERE id=?", [mtime, rootid])
            conn.commit()

        if scan_files:
            # First, delete deleted files from database
            c.execute("SELECT filename FROM files WHERE directory=?", [rootid])
            while True:
                row = c.fetchone()
                if not row:
                    break
                file_path = os.path.join(root, row[0])
                if not os.path.isfile(file_path):
                    print('File', file_path, 'doesnt exist, removing from db..')
                    c2 = conn.cursor()
                    c2.execute('DELETE FROM files WHERE directory=? AND filename=?', [rootid, row[0]])
            conn.commit()

            # Scan the existing files
            scanned_files = 0
            for filename in files:
                filedata = get_file_data(rootid, convert_name(filename))
                file_path = os.path.join(root, filename)
                mtime = os.path.getmtime(file_path)
                if filedata and mtime != filedata[1]:
                    print("mtime changed for ", filename, "deleting..")
                    c.execute("DELETE FROM files WHERE filename=? AND directory=?", [convert_name(filename), rootid])
                    conn.commit()
                    filedata = None
                if not filedata:
                    file_size = os.path.getsize(file_path)
                    scanned_files = scanned_files + 1
                    c.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?)", [rootid, convert_name(filename), file_size, mtime, None])
            conn.commit()
            if scanned_files > 0:
                print("Scanned " + str(scanned_files) + " files.")

    conn.close()

if args.operation == "scan":
    createTables()
    removeMissing()
    scan()
elif args.operation == "finddupes":
    finddupes()
exit(0)
