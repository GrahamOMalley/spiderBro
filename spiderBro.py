#! /usr/bin/python

#####################################################################################
#
# Script to scan thetvdb.com for series info, compare list of episodes to the xbmc
# mysql DB, and attempt to download missing torrents from piratebay/btjunkie
# using the deluge rpc interface
#
#####################################################################################
import socket
import time
from sb_utils import *

# globals
start_time = str(datetime.today()).split(".")[0].replace(" ", "_")
# dont change db_mask unless you want to delete the db and start over...
db_mask = sNeN()
# these could be made configurable
polite_value = 5
socket.setdefaulttimeout(10)
e_masks = [NxN, sNeN]
s_masks = [season, series]
search_list = [piratebaysearch, btjunkiesearch]

dl_these = []

config = ConfigParser.ConfigParser()
config.read("/home/gom/.spiderBro/config.ini")

# Attempt to get values from config file
try:
    use_whole_lib = config.getboolean("options", "scan_all_shows_xbmc")
except:
    use_whole_lib = False
try:
    polite = config.getboolean("options", "polite")
except:
    polite = False
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
        if(arg == "--learn" or arg == "-l"):
            force_learn = True
        if(arg == "--polite" or arg == "-p"):
            polite = True
        if(arg == "--verbose" or arg == "-v"):
            use_debug_logging = True
        if(arg == "--usexbmc" or arg == "-x"):
            use_whole_lib = True
        if(arg == "--help" or arg == "-h"):
            print "Usage:"
            print "spiderBro.py"
            print "Options:"
            print "\t--usexbmc or -x"
            print "\t\t Uses entire xbmc tv shows library"
            print "\t--learn or -l"
            print "\t\t forces spiderBro to mark all episodes it cannot find in db (usual behaviour is to ignore ones from current season)"
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
handler_file = logging.FileHandler('%s/spiderBro_%s.log' % (log_dir, start_time))
handler_file.setFormatter(formatter)
log.addHandler(handler_file)

log.info("Initiating Automatic Torrent Download [beep boop boop beep]")
log.debug("")
log.debug("Using params:")
log.debug("use_debug_logging: %s " % use_debug_logging)
log.debug("use_whole_lib: %s " % use_whole_lib)
log.debug("force_learn: %s " % force_learn)
log.debug("tv_dir: %s " % tv_dir)
log.debug("log_dir: %s " % log_dir)
log.debug("shows_file: %s " % shows_file)
log.debug("")

# If using the shows file, open and get shows list
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

# Get the list of shows that are complete so we can safely ignore them, speeds up whole library scan considerably in my case
ignore_list = []
tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
tmc = tempmysql_con.cursor()
tmc.execute("""select distinct * from finished_shows""")
for show in tmc:
    ignore_list.append(show[0])
tmc.close()
tempmysql_con.close()

shows_list = [val for val in shows_list if val not in ignore_list]

# The function that actually grabs our episodes
def hunt_eps(s):
    series_name = s
    dir = tv_dir + series_name.replace(" ", "_").replace("'", "").lower()
    ended = False
    log.info("Looking for eps for: %s" % (series_name))
    try:
        # get the series id from thetvdb.com
        page = urllib2.urlopen("http://cache.thetvdb.com/api/GetSeries.php?seriesname=%s" % urllib2.quote(series_name))
        if polite: time.sleep(polite_value)
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
                ep = i.episodenumber.string
                try:
                    fa = i.firstaired.string.split('-')
                    airdate = date(int(fa[0]), int(fa[1]), int(fa[2]))
                    # need to compare current date to air date, ignore if not aired yet
                    if date.today() > airdate:
                        aired_list.append((season, ep))
                except:
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
            have_list.append((str(cur[0]), str(cur[1])))

        mc.close()
        mysql_con.close()

        # create new db con to torrents db, populate from here aswell
        mysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
        tmc = mysql_con.cursor()
        tmc.execute("""select distinct episode from urls_seen where showname = \"%s\"""" % series_name)
        for cur in tmc:
            s = str(int(cur[0].split('e')[0].replace("s", "")))
            if("-" in cur[0].split('e')[1]):
                e = "-1"
            else:
                e = str(int(cur[0].split('e')[1]))
            have_list.append((s, e))
        tmc.close()
        mysql_con.close()

    except ValueError as v:
        log.error("Database error?")
        log.error(str(v))
        sys.exit()

    # TODO: if missing entire season
    have_s = list(set([h[0] for h in have_list]))
    aired_s = list(set([a[0] for a in aired_list]))
    if(ended):
        seas = [c for c in aired_s if c not in have_s]
    else:
        seas = [c for c in aired_s if((c not in have_s) and (int(c) < highest_season))]
    
    have_seas = [val for val in have_list if val[1] == "-1"]
    # get the episodes, search torrent sites for episodes
    ep_list = [val for val in aired_list if val not in have_list]
    for s in seas:
        ep_list = [c for c in ep_list if c[0] != s]
        ep_list.append((s, "-1"))
    for h in have_seas:
        ep_list = [c for c in ep_list if c[0] != h[0]]
    #sys.exit()

    if ended and not ep_list:
        log.info("Got all episodes for this, skipping in future")
        tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
        tmc = tempmysql_con.cursor()
        tmc.execute("""insert into finished_shows (showname) VALUES (\"%s\")""" % (series_name))
        tmc.close()
        tempmysql_con.close()
        return
    elif ep_list:
        for s, e in ep_list:
            found = False
            val = db_mask.mask(s, e)
            if(e == "-1"):
                log.info("Searching for entire season %s of %s" % (s, series_name))
                masks_list = s_masks
            else:
                masks_list = e_masks
            for site_ctor in search_list:
                if not found:
                    # if season use season mask list
                    for mk_ctor in masks_list:
                        if polite: time.sleep(polite_value)
                        mk = mk_ctor()
                        mskinf = mk.mask(s,e)
                        site = site_ctor()
                        log.info("\tSearching %s using mask %s" % (site.name, mskinf))
                        try:
                            url = site.search(series_name, s, e, mk_ctor)
                            if url:
                                log.info("\tFound torrent: %s" % url)
                                val = db_mask.mask(s, e)
                                dict = {'url':url, "save_dir":dir, 'showname':series_name, "episode":val}
                                dl_these.append(dict)
                                found = True
                                break
                        except AttributeError as ex:
                            log.error("%s timed out?" % ex)
                        except:
                            print "Unexpected error:", sys.exc_info()[0]
                            log.error("%s timed out?" % site.name)
            if not found:
                #check episode is not in current season, do not search again if so
                ep_season = int(s)
                if ((ep_season < highest_season) or (force_learn)):
                    log.info("Cannot find torrent for: %s %s - skipping this in future" % (series_name, val))
                    # insert into db
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
    # we get the complete list of shows from xbmc, minus the finished shows (if any)
    mysql_con = MySQLdb.connect (host = "localhost",user = "xbmc",passwd = "xbmc",db = "xbmc_video")
    mc = mysql_con.cursor()
    mc.execute("""select distinct strTitle from episodeview order by strTitle""")
    for show in mc:
        if(show[0] not in ignore_list):
            hunt_eps(show[0])
    mc.close()
    mysql_con.close()

else:
    if(shows_list):
        log.info("Using list of shows from file...")
        for show in shows_list:
            hunt_eps(show)
    else:
        log.info("No shows to download, exiting")
        sys.exit()


# Connect to a daemon running on the localhost
d = client.connect()
# We add the callback to the Deferred object we got from connect()
d.addCallback(on_connect_success)
# We add the callback (in this case it's an errback, for error)
d.addErrback(on_connect_fail)
# Run the twisted main loop to make everything go
reactor.run()
