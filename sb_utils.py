#! /usr/bin/env python
from BeautifulSoup import BeautifulSoup
from datetime import date
from datetime import datetime
from deluge.log import setupLogger
from deluge.ui.client import client
from twisted.internet import defer
from twisted.internet import reactor
import ConfigParser
import MySQLdb
import logging
import re
import string
import sys
import time
import urllib2

# nasty global
dl_these = []

#####################################################################################
# Filemasks
#####################################################################################

class season:
    def __init__(self):
        self.descr = "season"
    def mask(self, sn, ep):
        return ("season %s" % sn)

class series:
    def __init__(self):
        self.descr = "series"
    def mask(self, sn, ep):
        return ("series %s" % sn)

class sNeN:
    def __init__(self):
        self.descr = "sNeN"
    def mask(self, sn, ep):
        s = "s0" + sn if(int(sn)<10) else "s" + sn
        e = "e0" + ep if(int(ep)<10) else "e" + ep
        return (s+e)

class NxN:
    def __init__(self):
        self.descr = "NxN"
    def mask(self, sn, ep):
        e = "0" + ep if(int(ep)<10) else "e" + ep
        return ("%sx%s" % (sn, e))
       
#####################################################################################
# Searches
#####################################################################################

class piratebaysearch:
    def __init__(self):
        self.name = "piratebay"
    def search(self, series_name, sn, ep, fmask):
        is_torrent = re.compile(".*torrent$")
        series_name = "".join(ch for ch in series_name if ch not in ["!", "'"])
        m = fmask()
        val = m.mask(sn, ep)
        #piratebay torrents use _ as a delimiter
        search_url = "http://thepiratebay.org/search/"+"+".join(series_name.split(" ")).replace("'","")+"+"+"+".join(val.split(" ")) + "/0/7/0"
        response = urllib2.urlopen(search_url)
        search_page = response.read()
        sps = BeautifulSoup(search_page)
        links = sps.findAll('a', href=re.compile("^http"))
        url = ""
        for l in links:
            if(is_torrent.match(l['href'])):
                if("swesub" not in l['href'].lower()):
                    if ep == "-1":
                        # we are searching for a torrent of an entire season
                        val = val.replace(" ", "_").lower()
                        if (val in l['href'].lower() or (val.replace("_","_0") in l['href'].lower())):
                            url = l['href']
                            break
                    else:
                        # we are searching for an episode
                        if(val in l['href'].lower() and  "_".join(series_name.split(" ")).lower() in l['href'].lower()):
                            url = l['href']
                            break
        return url

class btjunkiesearch:
    def __init__(self):
        self.name = "btjunkie"
    def search(self, series_name, sn, ep, fmask):
        series_name = "".join(ch for ch in series_name if ch not in ["!", "'"])
        is_torrent = re.compile(".*torrent$")
        g = re.compile(r'Good\((.*?)\)', re.DOTALL)
        f = re.compile(r'Fake\((.*?)\)', re.DOTALL) 
        url = ""
        m = fmask()
        val = m.mask(sn, ep)
        search_url = "http://btjunkie.org/search?q="+"+".join(series_name.split(" ")).replace("'","")+"+"+"+".join(val.split(" "))
        response = urllib2.urlopen(search_url)
        search_page = response.read()
        response.close()
        sps = BeautifulSoup(search_page)
        links = sps.findAll('a', href=re.compile("^http"))
        if links:
            val = val.replace(" ", "-").lower()
            for l in links:
                good = 0
                fake = 0
                m_found = False
                if(is_torrent.match(l['href']) and ("swesub" not in l['href'].lower())):
                    if ep == "-1":
                        if (val in l['href'].lower() or (val.replace("-","-0") in l['href'].lower())):
                            m_found = True
                    else:
                        if(val in l['href'].lower() and  "-".join(series_name.split(" ")).lower() in l['href'].lower()):
                            m_found = True

                    if(m_found):
                        turl = l['href'].replace("/download.torrent", "").replace("dl.", "")
                        resp = urllib2.urlopen(turl)
                        # due to btjunkie having occasional broken/fake torrents, need some additional validation
                        validate_page = resp.read()
                        val_tags = BeautifulSoup(validate_page)
                        b = val_tags.findAll('b')
                        for bs in b:
                            if bs.string:
                                if g.match(bs.string):
                                    good = int(g.findall(bs.string)[0])
                                    li = bs.string.split(" ")
                                    for v in li:
                                        if f.match(v):
                                            fake = int(f.findall(v)[0])
                        if(good > fake):
                            url =l['href']
        return url

#####################################################################################
# Deferred callback function for clean exit
#####################################################################################

def dl_finish(result):
    l = logging.getLogger('spiderbro')
    l.info("All deferred calls have fired, exiting program...")
    client.disconnect()
    # Stop the twisted main loop and exit
    reactor.stop()

#####################################################################################
# Functions to retrieve configs, episodelists etc
#####################################################################################

def get_config_file(filename):
    opts = {}
    config = ConfigParser.ConfigParser()
    config.read(filename)
    
    # Attempt to get values from config file
    try:
        opts['use_whole_lib'] = config.getboolean("options", "scan_all_shows_xbmc")
    except:
        opts['use_whole_lib'] = False
    try:
        opts['polite'] = config.getboolean("options", "polite")
    except:
        opts['polite'] = False
    try:
        opts['polite_value'] = config.get("options", "polite_value")
    except:
        opts['polite_value'] = 5
    try:
        opts['force_learn'] = config.getboolean("options", "force_learn")
    except:
        opts['force_learn'] = False
    try:
        opts['tv_dir'] = config.get("options", "tv_dir")
    except:
        opts['tv_dir'] = "/media/twoTB1/videos/tv/"
    try:
        opts['shows_file'] = config.get("options", "shows_file")
    except:
        opts['shows_file'] = None
    try:
        opts['log_dir'] = config.get("options", "log_dir")
    except:
        opts['log_dir'] = "/home/gom/log"
    try:
        opts['use_debug_logging'] = config.getboolean("options", "use_debug_logging")
    except:
        opts['use_debug_logging'] = False
    return opts

def get_episode_list(series, o):
    aired_list = []
    have_list = []
    highest_season = 1
    ended = False
    series_name = series
    l = logging.getLogger("spiderbro")
    l.info("Looking for eps for: %s" % (series_name))
    try:
        # get the series id from thetvdb.com
        page = urllib2.urlopen("http://cache.thetvdb.com/api/GetSeries.php?seriesname=%s" % urllib2.quote(series_name))
        if o['polite']: time.sleep(o['polite_value'])
        soup = BeautifulSoup(page)
        series_id = soup.data.series.seriesid.string
        # now get the info for the series
        data = BeautifulSoup(urllib2.urlopen("http://thetvdb.com/data/series/%s/all/" % str(series_id))).data
        if(data.series.status.string == "Ended"):
            ended = True
        # data structures to keep track of episodes

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
        l.error("\tCould not get episode list from thetvdb (timeout?)")
        l.error("")
        return [], False, highest_season
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
        l.error("Database error?")
        l.error(str(v))
        sys.exit()

    have_s = list(set([h[0] for h in have_list]))
    aired_s = list(set([a[0] for a in aired_list]))
    if(ended):
        seas = [c for c in aired_s if c not in have_s]
    else:
        seas = [c for c in aired_s if((c not in have_s) and (int(c) < highest_season))]
    
    have_seas = [val for val in have_list if val[1] == "-1"]
    ep_list = [val for val in aired_list if val not in have_list]
    for s in seas:
        ep_list = [c for c in ep_list if c[0] != s]
        ep_list.append((s, "-1"))
    for h in have_seas:
        ep_list = [c for c in ep_list if c[0] != h[0]]
    return ep_list, ended, highest_season

def get_ignore_list():
    ig_l = []
    tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
    tmc = tempmysql_con.cursor()
    tmc.execute("""select distinct * from finished_shows""")
    for show in tmc:
        ig_l.append(show[0])
    tmc.close()
    tempmysql_con.close()
    return ig_l
 
def get_params(args):
    switches = ['--help', '--learn', '--polite', '--force_show', '--use_xbmc', '--verbose', '-h', '-l', '-p', '-s', '-v', '-x']
    opts = {}
    if len(args) > 1:
        for i in range(len(args)):
            if args[i] in switches:
                
                # --LEARN
                if(args[i] == "--learn" or args[i] == "-l"):
                    opts['force_learn'] = True
                
                # --USE_DEBUG_LOGGING
                if(args[i]== "--verbose" or args[i]== "-v"):
                    opts['use_debug_logging'] = True

                # --USE_XBMC
                if(args[i]== "--use_xbmc" or args[i]== "-x"):
                    opts['use_whole_lib'] = True

                # --SHOW
                if(args[i] == "--show" or args[i] == "-s"):
                    try:
                        if(args[i+1] not in switches):
                            opts['force_show'] = args[i+1]
                            opts['use_whole_lib'] = False
                        else:
                            print "please supply value for show to force"
                            sys.exit()
                    except:
                        print "please supply show to force"
                        sys.exit()
                
                # --POLITE
                if(args[i] == "--polite" or args[i] == "-p" ):
                    try:
                        if(args[i+1] not in switches):
                            opts['polite_value'] = int(args[i+1])
                            opts['polite'] = True
                        else:
                            print "please supply integer value for polite wait period"
                            sys.exit()
                    except:
                        print "please supply polite param in the form of an integer"
                        sys.exit()
                
                # --HELP
                if(args[i]== "--help" or args[i]== "-h"):
                    print "Usage:"
                    print "spiderBro.py"
                    print "Options:"
                    
                    print "\t--learn or -l"
                    print "\t\t forces spiderBro to mark all episodes it cannot find in db (usual behaviour is to ignore ones from current season)"
                    
                    print "\t--polite or -p"
                    print "\t\t forces spiderBro to wait n seconds before opening a url (to prevent site admins from banning you for wasting their bandwidth)"
                    
                    print "\t--show or -s"
                    print "\t\t Forces scan of only show X (will add new shows to library if not in current library)"

                    print "\t--verbose or -v"
                    print "\t\t Turns on debug logging"

                    print "\t--usexbmc or -x"
                    print "\t\t Uses entire xbmc tv shows library"

                    print "\t--help or -h"
                    print "\t\tPrint help and exit"
                    sys.exit()

    return opts

def get_sb_log(o):
    start_time = str(datetime.today()).split(".")[0].replace(" ", "_")
    setupLogger()
    l = logging.getLogger("spiderbro")
    if (o['use_debug_logging'] == True):
        l.setLevel(logging.DEBUG)
    else:
        l.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    handler_stream = logging.StreamHandler()
    handler_stream.setFormatter(formatter)
    handler_stream.setLevel(logging.CRITICAL)
    l.addHandler(handler_stream)
    handler_file = logging.FileHandler('%s/spiderBro_%s.log' % (o['log_dir'], start_time))
    handler_file.setFormatter(formatter)
    l.addHandler(handler_file)
    l.info("Initiating Automatic Torrent Download [beep boop boop beep]")
    log_debug_info(o)
    return l

def get_shows_from_file(fname):
    try:
        slist = []
        f = open(fname)
        try:
            for line in f:
                slist.append(line.replace("\n",""))
        finally:
            f.close()
            return slist
    except:
        log.error("Cannot open shows file, exiting")
        sys.exit()

#####################################################################################
# The function that actually grabs our episodes
#####################################################################################

def hunt_eps(series_name, opts, search_list, s_masks, e_masks, db_mask):
    l = logging.getLogger('spiderbro')
    dir = opts['tv_dir'] + series_name.replace(" ", "_").replace("'", "").lower()
    ep_list, ended, highest_season = get_episode_list(series_name, opts)
    # get the episodes, search torrent sites for episodes
    if ended and not ep_list:
        l.info("Got all episodes for this, skipping in future")
        tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
        tmc = tempmysql_con.cursor()
        tmc.execute("""insert into finished_shows (showname) VALUES (\"%s\")""" % (series_name))
        tmc.close()
        tempmysql_con.close()
        return {}
    elif ep_list:
        for s, e in ep_list:
            found = False
            val = db_mask.mask(s, e)
            if(e == "-1"):
                l.info("Searching for entire season %s of %s" % (s, series_name))
                masks_list = s_masks
            else:
                masks_list = e_masks
            for site_ctor in search_list:
                if not found:
                    # if season use season mask list
                    for mk_ctor in masks_list:
                        if opts['polite']: time.sleep(opts['polite_value'])
                        mk = mk_ctor()
                        mskinf = mk.mask(s,e)
                        site = site_ctor()
                        l.info("\tSearching %s using mask %s" % (site.name, mskinf))
                        try:
                            url = site.search(series_name, s, e, mk_ctor)
                            if url:
                                l.info("\tFound torrent: %s" % url)
                                val = db_mask.mask(s, e)
                                dict = {'url':url, "save_dir":dir, 'showname':series_name, "episode":val}
                                dl_these.append(dict)
                                found = True
                                return dict
                        except AttributeError as ex:
                            l.error("%s timed out?" % ex)
                        except:
                            print "Unexpected error:", sys.exc_info()[0]
                            l.error("%s timed out?" % site.name)
            if not found:
                #check episode is not in current season, do not search again if so
                ep_season = int(s)
                if ((ep_season < highest_season) or (opts['force_learn'])):
                    l.info("Cannot find torrent for: %s %s - skipping this in future" % (series_name, val))
                    # insert into db
                    tempmysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
                    tmc = tempmysql_con.cursor()
                    tmc.execute("""insert into urls_seen (showname,episode,url) VALUES (\"%s\",\"%s\",\"None\")""" % (series_name, val))
                    tmc.close()
                    tempmysql_con.close()
            l.info("")

#####################################################################################
# Print out some nice debugging info
#####################################################################################

def log_debug_info(o):
    l = logging.getLogger("spiderbro")
    l.debug("")
    l.debug("Using params:")
    sopts = o.keys()
    sopts.sort()
    for k in sopts:
        l.debug("%s: %s" % (k, o[k]))
    l.debug("")

#####################################################################################
# Deferred callback function to be called when an error is encountered
#####################################################################################

def on_connect_fail(result):
    l = logging.getLogger('spiderbro')
    l.info("Connection failed!")
    l.info("result: %s" % result)
    sys.exit()

#####################################################################################
# Deferred callback function called when we connect
#####################################################################################

def on_connect_success(result):
    l = logging.getLogger('spiderbro')
    init_list = []
    l.info("Connection to deluge was successful, result code: %s" % result)
    # need a callback for when torrent added completes
    def add_tor(key, val):
        l.info("Added torrent url to deluge: %s" % (val))
    
    mysql_con = MySQLdb.connect (host = "localhost",user = "torrents",passwd = "torrents",db = "torrents")
    tmc = mysql_con.cursor()
    for tp in dl_these:
        di = {'download_location':tp['save_dir']}
        df = client.core.add_torrent_url(tp["url"], di).addCallback(add_tor, tp["url"])
        init_list.append(df)
        #add url to database - ideally would be nice to do this in callback, but dont have info there?
        tmc.execute("""insert into urls_seen (showname,episode,url) VALUES (\"%s\",\"%s\",\"%s\")""" % (tp["showname"],tp["episode"],tp["url"]))
    tmc.close()
    dl = defer.DeferredList(init_list)
    dl.addCallback(dl_finish)

