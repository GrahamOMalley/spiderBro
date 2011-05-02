#! /usr/bin/python

#####################################################################################
#
# Script to scan thetvdb.com for series info, compare list of episodes to the xbmc
# mysql DB, and attempt to download missing torrents from piratebay/btjunkie
# using the deluge rpc interface
#
#####################################################################################

import urllib2
from BeautifulSoup import BeautifulSoup
from datetime import date
from datetime import datetime
import MySQLdb
import re
from deluge.ui.client import client
from twisted.internet import defer
from twisted.internet import reactor
from deluge.log import setupLogger
import logging
import sys
import ConfigParser
import string

# globals
start_time = str(datetime.today()).split(".")[0].replace(" ", "_")
dl_these = []


config = ConfigParser.ConfigParser()
config.read("/home/gom/.autotorrent/config.ini")

# Attempt to get values from config file
try:
    use_whole_lib = config.getboolean("options", "scan_all_shows_xbmc")
except:
    use_whole_lib = False
try:
    force_learn = config.getboolean("options", "force_learn")
except:
    force_learn = False
try:
    tv_dir = config.get("options", "tv_dir")
except:
    tv_dir = "/media/twoTB1/videos/tv/"
try:
    shows_file = config.get("options", "shows_file")
except:
    shows_file = None
try:
    log_dir = config.get("options", "log_dir")
except:
    log_dir = "/home/gom/log"
try:
    use_debug_logging = config.getboolean("options", "use_debug_logging")
except:
    use_debug_logging = False


# parse arg list - this will override anything in the config file that conflicts
if len(sys.argv) > 1:
    for arg in sys.argv:
        if(arg == "--verbose" or arg == "-v"):
            use_debug_logging = True
        if(arg == "--usexbmc" or arg == "-x"):
            use_whole_lib = True
        if(arg == "--learn" or arg == "-l"):
            force_learn = True
        if(arg == "--help" or arg == "-h"):
            print "Usage:"
            print "autotorrent.py"
            print "Options:"
            print "\t--usexbmc or -x"
            print "\t\t Uses entire xbmc tv shows library"
            print "\t--learn or -l"
            print "\t\t forces autotorrent to mark all episodes it cannot find in db (usual behaviour is to ignore ones from current season)"
            print "\t--help or -h"
            print "\t\tPrint help and exit"
            sys.exit()

# Set up the logger to print out errors
setupLogger()
log = logging.getLogger("test.log")
if (use_debug_logging):
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
handler_stream = logging.StreamHandler()
handler_stream.setFormatter(formatter)
handler_stream.setLevel(logging.CRITICAL)
log.addHandler(handler_stream)
handler_file = logging.FileHandler('%s/auto_torrent_%s.log' % (log_dir, start_time))
handler_file.setFormatter(formatter)
log.addHandler(handler_file)

log.info("Initiating Automatic Torrent Download [beep boop boop beep]")
log.debug("")
log.debug("Using params:")
log.debug("use_whole_lib: %s " % use_whole_lib)
log.debug("force_learn: %s " % force_learn)
log.debug("tv_dir: %s " % tv_dir)
log.debug("shows_file: %s " % shows_file)
log.debug("log_dir: %s " % log_dir)
log.debug("use_debug_logging: %s " % use_debug_logging)
log.debug("")


shows_list = []
if(shows_file and not use_whole_lib):
	try:
		f = open(shows_file)
		try:
			for line in f:
				shows_list.append(line.replace("\n",""))
		finally:
			f.close()
	except:
		log.error("Cannot open shows file, exiting")
		sys.exit()

ignore_list = []

tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
tmc = tempmysql_con.cursor()
tmc.execute("""select distinct * from finished_shows""")
for show in tmc:
    ignore_list.append(show[0])
tmc.close()
tempmysql_con.close()

shows_list = [val for val in shows_list if val not in ignore_list]
# some regexs we will be using
g = re.compile(r'Good\((.*?)\)', re.DOTALL) 
f = re.compile(r'Fake\((.*?)\)', re.DOTALL) 
is_torrent = re.compile(".*torrent$")

def hunt_eps(s):
    series_name = s
    ended = False
    log.info("Looking for eps for: %s" % (series_name))
    try:
		# get the series id from thetvdb.com
        dir = tv_dir + series_name.replace(" ", "_").replace("'", "").lower()
        page = urllib2.urlopen("http://cache.thetvdb.com/api/GetSeries.php?seriesname=%s" % urllib2.quote(series_name))
        soup = BeautifulSoup(page)
        series_id = soup.data.series.seriesid.string
		# now get the info for the series
        data = BeautifulSoup(urllib2.urlopen("http://thetvdb.com/data/series/%s/all/" % str(series_id))).data
        if(data.series.status.string == "Ended"):
            ended = True
		# data structures to keep track of episodes
        aired_list = []
        have_list = []
        highest_season = 1

        # iterate through data, get list of season/episodes for show starting from 1 (0 are specials)
        for i in data.findAll('episode', recursive=False):
            if(i.seasonnumber.string != '0'):
       	        season = i.seasonnumber.string
    	        highest_season = max(highest_season, int(i.seasonnumber.string))
            	if(int(season) < 10): season = '0' + season
                ep = i.episodenumber.string
                if(int(ep) < 10): ep = '0' + ep
                try:
                    fa = i.firstaired.string.split('-')
                    airdate = date(int(fa[0]), int(fa[1]), int(fa[2]))
                    # need to compare current date to air date, ignore if not aired yet
                    if date.today() > airdate:
                        aired_list.append("s"+season+"e"+ep)
                except:
                    #log.debug(debu)
                    pass
    except:
        log.error("\tCould not get episode list from thetvdb (timeout?)")
        log.error("")
        return
    
    # use the mysql lib to access xbmc db, cross check episode lists
    try:
        mysql_con = MySQLdb.connect (host = "localhost",user = "xbmc",passwd = "xbmc",db = "xbmc_video")
        mc = mysql_con.cursor()
        # SELECT season number, episode number from show
        mc.execute("""select c12,c13 from episodeview where strtitle = \"%s\"""" % series_name)
        for cur in mc:
            season = cur[0]
            ep = cur[1]
            if(int(season) < 10): season = '0' + season
            if(int(ep) < 10): ep = '0' + ep
            have_list.append("s"+season+"e"+ep)

        mc.close()
        # create new db con to torrents db, populate from here aswell

        mysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
        tmc = mysql_con.cursor()
        tmc.execute("""select distinct episode from urls_seen where showname = \"%s\"""" % series_name)
        for cur in tmc:
            have_list.append(cur[0])
        tmc.close()

    except:
        log.error("Database error?")

    # get the episodes, search torrent sites for episodes
    ep_list = [val for val in aired_list if val not in have_list]
    if ended and not ep_list:
        log.info("Got all episodes for this, cache in new table")
        tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
        tmc = tempmysql_con.cursor()
        tmc.execute("""insert into finished_shows (showname) VALUES (\"%s\")""" % (series_name))
        tmc.close()
        tempmysql_con.close()
        return
    elif ep_list:
        for val in ep_list:
            found = False
            log.info("\tSearching thepiratebay.org for: %s" % (val))
            search_url = "http://thepiratebay.org/search/" + "+".join(series_name.split(" ")).replace("'","") + "+" + val + "/0/7/0"
            try:
                response = urllib2.urlopen(search_url)
                search_page = response.read()
                sps = BeautifulSoup(search_page)
                links = sps.findAll('a', href=re.compile("^http"))
                if links:
                    if(is_torrent.match(links[0]['href'])):
                        if(val in links[0]['href'].lower()):
                            if("swesub" not in links[0]['href'].lower()):
                                log.info("\t\tFound torrent: %s" % (links[0]['href']))
                                t = links[0]['href'], dir
                                dict = {'url': links[0]['href'], "save_dir":dir, 'showname':series_name, "episode":val}
                                dl_these.append(dict)
                                found = True
            except:
                log.error("Pirate bay timed out?")

            if not found:
	            #search btjunkie too
	            log.info("\tSearching www.btjunkie.org for: %s" % (val))
	            good = 0
	            fake = 0
	            search_url = "http://btjunkie.org/search?q=" + "+".join(series_name.split(" ")).replace("'","") + "+" + val
	            response = urllib2.urlopen(search_url)
	            search_page = response.read()
	            response.close()
	            sps = BeautifulSoup(search_page)
	            links = sps.findAll('a', href=re.compile("^http"))
	            if links:
	                if(is_torrent.match(links[0]['href'])):
	                    if(val in links[0]['href'].lower()):
	                        # dont want episodes with the "swesub" tag in them
	                        # TODO: if this becomes a problem, create a list of undesirable tags
	                        if("swesub" not in links[0]['href'].lower()):
	                            log.info("\t\tFound torrent: " + (links[0]['href']))
	                            turl = links[0]['href'].replace("/download.torrent", "").replace("dl.", "")
	                            resp = urllib2.urlopen(turl)
	                            validate_page = resp.read()
	                            val_tags = BeautifulSoup(validate_page)
	                            b = val_tags.findAll('b')
	                            for bs in b:
	                                if bs.string:
	                                    if g.match(bs.string):
	                                        good = int(g.findall(bs.string)[0])
	                                        l = bs.string.split(" ")
	                                        for v in l:
	                                            if f.match(v):
	                                                fake = int(f.findall(v)[0])
	
                                if(good > fake):
                                    log.info("\t\tTorrent Validated, adding...")
                                    t = links[0]['href'], dir
                                    dict = {'url': links[0]['href'], "save_dir":dir, 'showname':series_name, "episode":val}
                                    dl_these.append(dict)
                                    found = True
                                else:
                                    log.info("\t\tTorrent failed validation! Good:%s Fake:%s" % (str(good), str(fake)))
            if not found:
                #check episode is not in current season, do not search again if so
                ep_season = int(val.split("e")[0].replace("s", ""))
                if ((ep_season < highest_season) or (force_learn)):
                    log.info("Cannot find torrent for: %s %s - skipping this in future" % (series_name, val))
                    #cache in db
                    tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
                    tmc = tempmysql_con.cursor()
                    tmc.execute("""insert into urls_seen (showname,episode,url) VALUES (\"%s\",\"%s\",\"None\")""" % (series_name, val))
                    tmc.close()
                    tempmysql_con.close()
            log.info("")

# deferred for clean exit
def dlfinish(result):
    log.info("All deferred calls have fired, exiting program...")
    client.disconnect()
    # Stop the twisted main loop and exit
    reactor.stop()

# def deluge client callbacks here
def on_connect_success(result):
    init_list = []
    log.info("Connection to deluge was successful, result code: %s" % result)
    # need a callback for when torrent added completes
    def add_tor(key, val):
	    log.info("Added torrent url to deluge: %s" % (val))
    
    mysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
    tmc = mysql_con.cursor()
    for tp in dl_these:
        di = {'download_location':tp['save_dir']}
        df = client.core.add_torrent_url(tp["url"], di).addCallback(add_tor, tp["url"])
        init_list.append(df)
		#add url to database - ideally would be nice to do this in callback, but dont have info there?
    	tmc.execute("""insert into urls_seen (showname,episode,url) VALUES (\"%s\",\"%s\",\"%s\")""" % (tp["showname"],tp["episode"],tp["url"]))
    tmc.close()
    log.debug("Init list: %s" % init_list)
    dl = defer.DeferredList(init_list)
    dl.addCallback(dlfinish)

# We create another callback function to be called when an error is encountered
def on_connect_fail(result):
    print "Connection failed!"
    print "result:", result
    sys.exit()

if(use_whole_lib):
    log.info("Scanning entire XBMC library, this could take some time...")
    # If we're feeling adventurous, we can get the complete list of shows from xbmc (this takes FOREVER to scrape the info though)
    mysql_con = MySQLdb.connect (host = "localhost",user = "xbmc",passwd = "xbmc",db = "xbmc_video")
    mc = mysql_con.cursor()
    mc.execute("""select distinct strTitle from episodeview order by strTitle""")
    for show in mc:
        if(show[0] not in ignore_list):
            hunt_eps(show[0])

else:
    if(shows_list):
        log.info("Using list of shows from file...")
        for show in shows_list:
	        hunt_eps(show)
    else:
        log.info("No shows to download, exiting")
        sys.exit()


# Connect to a daemon running on the localhost
# We get a Deferred object from this method and we use this to know if and when
# the connection succeeded or failed.
d = client.connect()
# We add the callback to the Deferred object we got from connect()
d.addCallback(on_connect_success)
# We add the callback (in this case it's an errback, for error)
d.addErrback(on_connect_fail)
# Run the twisted main loop to make everything go
reactor.run()
