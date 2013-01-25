#! /usr/bin/env python
import sys 
import os
import shutil
import sqlite3
import subprocess
import fnmatch
import logging
import gomXBMCTools

dbfile = "/home/gom/code/python/spider_bro/spiderbro.db" 
target = "/media/tv2/"

logging.basicConfig(filename='/home/gom/log/sb_file_renamer.log',level=logging.DEBUG)
logging.info('')
logging.info('File Renamer Started...')
logging.info('Target Dir to write files is: %s' % target)

name = sys.argv[2]
path = sys.argv[3]
logging.info('Torrent name is: %s' % sys.argv[2])
logging.info('Torrent save path is: %s' % sys.argv[3])

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
            logging.info("Unrar: Extracted %s" % filePath)
        else:
            logging.info("Unrar: Error exctracting %s" % filePath)
    else:
        logging.info("Unrar: Unable to find unrar executable")


if (not os.path.exists(dbfile)):
    logging.info("cannot find db...")
    sys.exit()
else:
    files_to_copy = []
    # spiderbro stores path
    conn = sqlite3.connect(dbfile)
    cur = conn.cursor()
    sname = path
    select = "select * from urls_seen where savepath like \"%" + sname + "%\""
    logging.info( "Trying to execute: ", select)
    for c in(cur.execute(select)):
        file_path = path+"/"+name
        file_to_copy = path+"/"+name
        if(os.path.isdir(file_path)):
            # 'Sample' files screw up logic if they are not deleted first
            for root, dirs, files in os.walk(file_path):
                for dirname in fnmatch.filter(dirs, "*Sample*"):
                    logging.info( "Sample dir detected, deleting... ", dirname)
                    shutil.rmtree(os.path.join(root,dirname))

            # walk dir, find any zip or rar
            logging.info( "Checking for archives...")
            for pattern in ("*.zip", "*.rar"):
                for root, dirs, files in os.walk(file_path):
                    for filename in fnmatch.filter(files, pattern):
                        # extract files
                        archive_file = ( os.path.join(root, filename))
                        logging.info( archive_file)
                        if pattern == "*.rar":
                            logging.info( "trying to unrar...")
                            unrar(archive_file)
                        else:
                            # TODO: implement unzip
                            logging.info( "trying to unzip")
            
            # walk dir, find any video files 
            for root, dirs, files in os.walk(file_path):
                for vfilename in filter(is_video_file, files):
                    logging.info( "FILE TO COPY IS: ", vfilename)
                    # set file to the correct file 
                    files_to_copy.append( os.path.join(root, vfilename))

        #  use creation logic from backup_tv.py to mv and rename episode
        s = "0" + str(c[1]) if(int(c[1])<10) else str(c[1])
        season_dir = "season_" + s
        series_name = gomXBMCTools.normaliseTVShowName(str(c[0]))

        if not os.path.isdir(target + series_name): 
            logging.info( "\tDirectory: ", series_name, " does not exist, creating...")
            os.mkdir(target+series_name)
        
        if not os.path.isdir(target + series_name + "/" + season_dir):
            logging.info( "\tDirectory: ", season_dir, " does not exist, creating...")
            os.mkdir(target + series_name + "/" + season_dir)
       
        for f in files_to_copy:
            e = "e0" + str(c[2]) if(int(c[2])<10) else "e" + str(c[2])
            if( c[2] == -1): e = gomXBMCTools.getEpisodeNumFromFilename(f, s)
            fileName, fileExtension = os.path.splitext(f)
            ftarget = target + series_name  + "/" + season_dir + "/" + series_name + "_s"+ s + e + fileExtension
            logging.info( "\tCopying ", f, " to ", ftarget)
            shutil.copy2(f, ftarget)
        
        #shutil.rmtree(path)
