#! /usr/bin/env python
import sys 
from datetime import datetime
import os
import shutil
import sqlite3
import subprocess
import fnmatch
import logging
import gomXBMCTools

dbfile = "/home/gom/code/python/spider_bro/spiderbro.db" 
logdir= "/home/gom/log/spiderbro"
target = "/media/nasGom/video/tv/"
id = sys.argv[1]
name = sys.argv[2]
path = sys.argv[3]
start_time = str(datetime.today()).split(".")[0].replace(" ", "_")
start_day = str(datetime.today()).split(" ")[0]

logger = logging.getLogger('filerenamer')
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
handler_stream = logging.StreamHandler()
handler_stream.setFormatter(formatter)
handler_stream.setLevel(logging.CRITICAL)
logger.addHandler(handler_stream)
handler_file = logging.FileHandler('%s/spiderBro_%s.log' % (logdir, start_day))
handler_file.setFormatter(formatter)
logger.addHandler(handler_file)
logger.setLevel(logging.INFO)
logger.info('')
logger.info('File Renamer Started...')
logger.info('Target Dir to write files is: %s' % target)

logger.info('Torrent id is: %s' % sys.argv[1])
logger.info('Torrent name is: %s' % sys.argv[2])
logger.info('Torrent save path is: %s' % sys.argv[3])
#sys.exit()

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
        logger.info("Unrar: Extracting %s" % filePath)
        r = subprocess.Popen(command, cwd=rardir,shell=False).wait()
        if r == 0:
            logger.info("Unrar: Extracted %s" % filePath)
        else:
            logger.info("Unrar: Error exctracting %s" % filePath)
    else:
        logger.info("Unrar: Unable to find unrar executable")


if (not os.path.exists(dbfile)):
    logger.info("cannot find db...")
    sys.exit()
else:
    files_to_copy = []
    # spiderbro stores path
    conn = sqlite3.connect(dbfile)
    cur = conn.cursor()
    sname = path
    select = "select * from urls_seen where savepath like \"%" + sname + "%\""
    logger.info( "Retrieving ep info with query: %s" % (select))
    for c in(cur.execute(select)):
        file_path = path+"/"+name
        file_to_copy = path+"/"+name
        logger.info("Filepath: %s" % (file_path))
        if(not os.path.isdir(file_path)):
            # we just have a single video file, copy
            files_to_copy.append(file_path)
        else:
            # we have a dir and are not sure whats in it, do some file manipulation before copying

            # 'Sample' files screw up logic if they are not deleted first
            logger.info( "Checking for sample...")
            for root, dirs, files in os.walk(file_path):
                for dirname in fnmatch.filter(dirs, "*Sample*"):
                    logger.info( "Sample dir detected, deleting... ", dirname)
                    shutil.rmtree(os.path.join(root,dirname))

            # walk dir, find any zip or rar
            logger.info( "Checking for archives...")
            for pattern in ("*.zip", "*.rar"):
                for root, dirs, files in os.walk(file_path):
                    for filename in fnmatch.filter(files, pattern):
                        # extract files
                        archive_file = ( os.path.join(root, filename))
                        logger.info( archive_file)
                        if pattern == "*.rar":
                            logger.info( "trying to unrar...")
                            unrar(archive_file)
                        else:
                            # TODO: implement unzip
                            logger.info( "trying to unzip")
            
            logger.info( "Checking for video files...")
            # walk dir, find any video files 
            for root, dirs, files in os.walk(file_path):
                for vfilename in filter(is_video_file, files):
                    logger.info( "Found file: %s" % (vfilename))
                    files_to_copy.append( os.path.join(root, vfilename))

        #  use creation logic from backup_tv.py to mv and rename episode
        s = "0" + str(c[1]) if(int(c[1])<10) else str(c[1])
        season_dir = "season_" + s
        series_name = gomXBMCTools.normaliseTVShowName(str(c[0]))

        if not os.path.isdir(target + series_name): 
            logger.info( "\tDirectory: %s does not exist, creating..." % (series_name))
            os.mkdir(target+series_name)
        
        if not os.path.isdir(target + series_name + "/" + season_dir):
            logger.info( "\tDirectory: %s does not exist, creating..." % (season_dir))
            os.mkdir(target + series_name + "/" + season_dir)
       
        rmdir = True
        for f in files_to_copy:
            e = "e0" + str(c[2]) if(int(c[2])<10) else "e" + str(c[2])
            # TODO: this is broken
            if( c[2] == -1): 
                e = gomXBMCTools.getEpisodeNumFromFilename(f, s)

            if( e != "e-1" ):
                fileName, fileExtension = os.path.splitext(f)
                ftarget = target + series_name  + "/" + season_dir + "/" + series_name + "_s"+ s + e + fileExtension
                logger.info( "--->  Copying File: %s to %s" % (f, ftarget))
                shutil.copy2(f, ftarget)
            else:
                logger.info("Copying file without renaming: %s" % (f))
                ftarget = target + series_name  + "/" + season_dir + "/" 
                shutil.copy2(f, ftarget)
                #rmdir = False
        if rmdir:
            logger.info("Cleaning up temporary dir %s" % (path))
            shutil.rmtree(path)

        from deluge.ui.client import client
        from twisted.internet import reactor, defer
        from deluge.log import setupLogger
        setupLogger()

        def printSuccess(dresult, is_success, smsg):
            print "[+]", smsg

        def printError(emsg):
            print "[e]", emsg

        def printReport(rresult):
            print rresult

        def dl_finish(result):
            print "All deferred calls have fired, exiting program..."
            client.disconnect()
            # Stop the twisted main loop and exit
            reactor.stop()

        def on_connect_fail(result):
            print "Connection failed!"
            print "result:", result

        def on_connect_success(result):
            print "Connection was successful!"
            torrent_id = id
            tlist = []
            successmsg = " Removed"
            errormsg = "Error removing"
            do_remove_data = False
            tlist.append(client.core.remove_torrent(torrent_id, do_remove_data).addCallbacks(printSuccess, printError, callbackArgs = (True, successmsg), errbackArgs = (errormsg)))
            defer.DeferredList(tlist).addCallback(printReport)
            defer.DeferredList(tlist).addCallback(dl_finish)

        d = client.connect()
        d.addCallback(on_connect_success)
        d.addErrback(on_connect_fail)
        reactor.run()
