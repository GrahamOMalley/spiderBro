#! /usr/bin/env python
import sys 
import os
import shutil
import unicodedata
import sqlite3
import subprocess
import fnmatch
import logging

logging.basicConfig(filename='/home/gom/log/sb_file_renamer.log',level=logging.DEBUG)
logging.info('File Renamer Started...')

target = "/media/tv2/"
logging.info('Target Dir to write files is: %s' % target)

name = sys.argv[2]
path = sys.argv[3]
logging.info('Arg1 is: %s' % sys.argv[1])
logging.info('Arg2 is: %s' % sys.argv[2])
logging.info('Arg3 is: %s' % sys.argv[3])


def is_video_file(filename, extensions=['.avi', '.mkv', '.mp4', '.flv', '.divx', '.mpg', '.mpeg', '.wmv']):
    return any(filename.lower().endswith(e) for e in extensions)

def findInPath(prog):
    for path in os.environ["PATH"].split(os.pathsep):
        exe_file = os.path.join(path, prog)
        if os.path.exists(exe_file) and os.access(exe_file, os.X_OK):
            return exe_file
        return False

def unrar(filePath):
    unrarprog = "unrar"
    if unrarprog:
        rardir=os.path.dirname(filePath)
        command=[unrarprog,'e',filePath]
        logging.info("Unrar: Extracting %s" % filePath)
        r = subprocess.Popen(command, cwd=rardir,shell=False).wait()
        if r == 0:
            print("Unrar: Extracted %s" % filePath)
            logging.info("Unrar: Extracted %s" % filePath)
        else:
            print("Unrar: Error exctracting %s" % filePath)
            logging.info("Unrar: Error exctracting %s" % filePath)
    else:
        print("Unrar: Unable to find unrar executable")
        logging.info("Unrar: Unable to find unrar executable")


if (not os.path.exists("/home/gom/code/python/spider_bro/spiderbro.db")):
    print "cannot find db..."
    logging.info("cannot find db...")
    sys.exit()
else:
    #       modify spiderbro to store path as uid like torrent_dir/community/2/12/
    conn = sqlite3.connect("/home/gom/code/python/spider_bro/spiderbro.db")
    cur = conn.cursor()
    sname = name.replace("[", "%5B").replace("]", "%5D") 
    sname = path
    select = "select * from urls_seen where savepath like \"%" + sname + "%\""
    print "Trying to execute: ", select
    logging.info( "Trying to execute: ", select)
    for c in(cur.execute(select)):
        print c
        logging.info( c)

        file_path = path+"/"+name
        file_to_copy = path+"/"+name
        if(os.path.isdir(file_path)):
            print "Dir detected, checking for archives..."
            logging.info( "Dir detected, checking for archives...")
            # walk dir, find any zip or rar
            for pattern in ("*.zip", "*.rar"):
                for root, dirs, files in os.walk(file_path):
                    for filename in fnmatch.filter(files, pattern):
                        # extract files
                        archive_file = ( os.path.join(root, filename))
                        print archive_file
                        logging.info( archive_file)
                        if pattern == "*.rar":
                            print "trying to unrar..."
                            logging.info( "trying to unrar...")
                            unrar(archive_file)
                        else:
                            print "trying to unzip"
                            logging.info( "trying to unzip")

            # walk dir, find any video files 
            for root, dirs, files in os.walk(file_path):
                for vfilename in filter(is_video_file, files):
                    print "FILE TO COPY IS: ", vfilename
                    logging.info( "FILE TO COPY IS: ", vfilename)
                    # set file to the correct file 
                    file_to_copy= ( os.path.join(root, vfilename))




        #  use creation logic from backup_tv.py to mv and rename episode

        s = "0" + str(c[1]) if(int(c[1])<10) else str(c[1])
        e = "e0" + str(c[2]) if(int(c[2])<10) else "e" + str(c[2])
        season_dir = "season_" + s
        series_name = str.lower(str(c[0]))
        series_name = series_name.replace("::", "")
        series_name = series_name.replace(": ", " ")
        series_name = series_name.replace(":", " ")
        series_name = "".join(ch for ch in series_name if ch not in ["!", "'", ":", "(", ")", ".", ","])
        series_name = series_name.replace("&", "and")
        series_name = series_name.replace(" ", "_") 

        # unicode screws up some shows, convert to latin-1 ascii
        series_name = unicode(series_name, "latin-1")
        unicodedata.normalize('NFKD', series_name).encode('ascii','ignore')

        fileName, fileExtension = os.path.splitext(file_to_copy)
        ftarget = target + series_name  + "/" + season_dir + "/" + series_name + "_s"+ s + e + fileExtension

        if not os.path.isdir(target + series_name): 
            print "\tDirectory: ", series_name, " does not exist, creating..."
            logging.info( "\tDirectory: ", series_name, " does not exist, creating...")
            os.mkdir(target+series_name)
        
        if not os.path.isdir(target + series_name + "/" + season_dir):
            print "\tDirectory: ", season_dir, " does not exist, creating..."
            logging.info( "\tDirectory: ", season_dir, " does not exist, creating...")
            os.mkdir(target + series_name + "/" + season_dir)
        
        print "\tCopying ", file_to_copy, " to ", ftarget
        logging.info( "\tCopying ", file_to_copy, " to ", ftarget)
        shutil.copy2(file_to_copy, ftarget)

        shutil.rmtree(path)
