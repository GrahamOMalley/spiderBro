#! /usr/bin/env python
import ConfigParser
import argparse
import logging
import re
import string
import sys
import time
import traceback
import urllib2
import gomXBMCTools
import json

from BeautifulSoup import BeautifulSoup
from datetime import date
from datetime import datetime
from deluge.log import setupLogger
from deluge.ui.client import client
from twisted.internet import defer
from twisted.internet import reactor

from db_manager import db_manager

#####################################################################################
# Filemasks
#####################################################################################

class Season:
    def __init__(self):
        self.descr = "Season"
    def mask(self, sn, ep):
        return ("season %s" % sn)

class Series:
    def __init__(self):
        self.descr = "Series"
    def mask(self, sn, ep):
        return ("series %s" % sn)

class SNEN:
    def __init__(self):
        self.descr = "SNEN"
    def mask(self, sn, ep):
        s = "s0" + sn if(int(sn)<10) else "s" + sn
        e = "e0" + ep if(int(ep)<10) else "e" + ep
        return (s+e)

class NxN:
    def __init__(self):
        self.descr = "NxN"
    def mask(self, sn, ep):
        e = "0" + ep if(int(ep)<10) else ep
        return ("%sx%s" % (sn, e))
       
class NNN:
    def __init__(self):
        self.descr = "NNN"
    def mask(self, sn, ep):
        e = "0" + ep if(int(ep)<10) else ep
        return ("%s%s" % (sn, e))
       
#####################################################################################
# Searches
#####################################################################################
class BaseSearch:
    def __init__(self):
        self.name = "Base Search Class"
        self.delimiter = " "
        self.can_get_tor_from_main_page = True

    def search(self, series_name, sn, ep, fmask, tags, is_high_qual):
        lg = logging.getLogger('spiderbro')
        series_name = series_name.replace("::", "")
        series_name = series_name.replace(": ", " ")
        series_name = series_name.replace(":", " ")
        series_name = "".join(ch for ch in series_name if ch not in ["!", "'", ":"])
        series_name = series_name.replace("&", "and")
        m = fmask()
        season_or_ep_str = m.mask(sn, ep)
        ser_list = self.generate_search_terms(series_name)
        is_season = False
        if ep == "-1": is_season = True
        for series_search_term in ser_list:
            search_url = self.get_search_url(series_search_term, season_or_ep_str)
            lg.info("\tSearching %s:\t%s %s \t\t(%s)" % (self.name, series_search_term, season_or_ep_str, search_url))
            try:
                #response = urllib2.urlopen(search_url)
                # TODO: add a headers member to the base search class
                # then have a loop here that builds up the request with the appropriate headers
                # the ones below work for extratorrent, use firefox dev edition to see what headers work on other sites
                request = urllib2.Request(search_url)
                request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
                request.add_header('User-Agent', "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:35.0) Gecko/20100101 Firefox/35.0")
                response = urllib2.urlopen(request)
                search_page = response.read()
                sps = BeautifulSoup(search_page)
                links = sps.findAll('a', href=re.compile(self.get_links_from_main_page_re()))
                for l in links:
                    if self.validate_link(series_search_term, season_or_ep_str, l['href'], tags, is_high_qual, is_season):
                        if self.validate_page(l['href']):
                            if self.can_get_tor_from_main_page:
                                return l['href']
                            else:
                                return self.get_torrent_from_validated_page(l['href'])
            except:
                lg.error("Couldn't open %s" % search_url)
                #lg.error("Shutting down sb, check that url is accessible")
                #sys.exit()
        return ""

    def get_links_from_main_page_re(self):
        lg = logging.getLogger('spiderbro')
        lg.debug("\tbase: get links from main page using regexp: ^http")
        return "^http"

    def get_torrent_from_validated_page(self, page):
        lg = logging.getLogger('spiderbro')
        lg.debug("base: get torrent from validated page using regexp: \"\"")
        return ""

    def validate_link(self, series, s_ep_str, link, tags, is_high_q, is_season):
        lg = logging.getLogger('spiderbro')
        # First validate the link title is ok
        is_torrent = re.compile(self.get_is_link_a_torrent_re())
        if(not is_torrent.match(link)):
            return False
        else:
            lg.debug('\t\tValidating %s' % (gomXBMCTools.getTorrentNameFromMagnetLink(link)))
            
        if (is_high_q and not (("720p" in link.lower()) or ("1080p" in link.lower()))): 
            lg.debug("\t\t\tValidation FAILED: Quality is HighQ but 720p not found in torrent")
            return False

        if ( not is_high_q and (("720p" in link.lower()) or ("1080p" in link.lower()))): 
            lg.debug("\t\t\tValidation FAILED: Quality is lowQ but 720p found in torrent")
            return False

        for t in tags:
            if t.lower() in link.lower(): 
                lg.debug("\t\t\tValidation FAILED: tag filter %s found in torrent" % t)
                return False
        
        if is_season: 
            # we are searching for a torrent of an entire season
            s_ep_str = s_ep_str.replace(" ", self.delimiter).lower()
            if (s_ep_str in link.lower() or (s_ep_str.replace(self.delimiter, self.delimiter+"0") in link.lower())):
                return True
        else:
            # we are searching for an episode
            delims = [self.delimiter, "."]
            for d in delims:
                if (self.validate_delims(series, s_ep_str, d, link)):
                    return True
                else:
                    lg.debug("\t\t\tValidation FAILED: s_ep_str %s or %s not found in link title" % (s_ep_str, d.join(series.split(" ")).lower()))
        
        return False

    def validate_delims(self, series, s_ep_str, delim, link):
        if (s_ep_str in link.lower() and  d.join(series.split(" ")).lower() in link.lower()):
            return True
        return False

    # child classes can define their own site-specific page validation, see PirateBaySearch for an example
    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\tbase: validate page (return true)")
        return True

    # break the series name up and try different variations of it 
    # eg: "Blah & Blah (2010)" -> ["Blah & Blah (2010)", "Blah & Blah", "Blah and Blah (2010)", "Blah and Blah"] etc
    def generate_search_terms(self, name):
        regser = re.compile(" \([0-9a-zA-Z]{2,4}\)").sub('', name)
        li = [name, regser]
        
        hli =[]
        for l in li:
            hyphen = " ".join(l.split("-"))
            hli.append(hyphen)
        if hli: li.extend(hli)

        for l in li:
            hyphen = " ".join(l.split(":"))
            hli.append(hyphen)
        if hli: li.extend(hli)

        cli =[]
        for l in li:
            comma = " ".join(l.split(","))
            cli.append(comma)
        if cli: li.extend(cli)


        ali =[]
        for l in li:
            ampersand = "and".join(l.split("&"))
            ali.append(ampersand)
        if cli: li.extend(ali)

        return list(set(li))
    
    def get_search_url(self, name, maskval):
        return "www.thisisabaseclassyouidiot.com"

    def get_is_link_a_torrent_re(self):
        return ".*torrent$"

# Child classes need to define self.delimiter, get_search_url and optionally validate_page 
class PirateBaySearch(BaseSearch):
    def __init__(self):
        self.name = "piratebay"
        self.delimiter = "+"
        self.can_get_tor_from_main_page = True

    def get_is_link_a_torrent_re(self):
        return "^magnet"

    def get_links_from_main_page_re(self):
        lg = logging.getLogger('spiderbro')
        lg.debug("\tpiratebay: get links from main page using regexp: ^magnet")
        return "^magnet"

    def get_search_url(self, name, maskval):
        return "http://pirateproxy.bz/search/"+"+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" ")) + "/0/7/0"
    
    def validate_page(self, tor):
        return True
        seeds = 0
        seeds_reg = re.compile("Seeders:</dt>\n<dd>[0-9]{1,9}")
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing piratebay page validation")
        turl = tor.replace("http://torrents.pirateproxy.bz", "http://pirateproxy.bz/torrent")
        resp = urllib2.urlopen(turl)
        html = resp.read()
        data = BeautifulSoup(html)
        details = data.findAll("dl", { "class" : "col2" })
        # This is ugly as sin, I think beautifulsoup has some problems with <dt> and <dd> tags?
        for d in details: 
            try:
                seeds = int(seeds_reg.findall(str(d))[0].replace("Seeders:</dt>\n<dd>", ""))
            except:
                lg.error("\t\tError parsing seeders for piratebay")
        if seeds > 0:
            lg.debug("\t\tValidation passed, torrent has %s seeds..." % seeds)
            return True
        else:
            lg.debug("\t\tValidation FAILED, torrent has no seeds...")
        return False

class KATSearch(BaseSearch):
    def __init__(self):
        self.name = "kickasstorrents"
        self.delimiter = "+"
        self.can_get_tor_from_main_page = True

    def get_is_link_a_torrent_re(self):
        return "^magnet"

    def get_links_from_main_page_re(self):
        return "^magnet"

    def get_search_url(self, name, maskval):
        return "https://kickass.unblocked.pw/usearch/" + " ".join(name.split(" ")).replace("'","")+" "+" ".join(maskval.split(" ")) + "/"

    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing KAT page validation for: "+tor)
        lg.debug("\t\tNot Implemented: extratorrent page validation, returning true")
        return True

    def get_torrent_from_validated_page(self, page):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tConverting torrent url to kat format : "+page)
        return "http://kickass.unblocked.pw/" + page.replace("torrent_", "")
    
    def validate_delims(self, series, s_ep_str, delim, link):
        series = series.replace(".","+")
        DEUBGME= delim.join(series.split(" ")).lower() 
        if (s_ep_str in link.lower() and  delim.join(series.split(" ")).lower() in link.lower()):
            return True
        return False

class ExtraTorrentSearch(BaseSearch):
    def __init__(self):
        self.name = "extratorrent"
        self.delimiter = "."
        self.can_get_tor_from_main_page = False

    def get_links_from_main_page_re(self):
        return ".*torrent$"

    def get_search_url(self, name, maskval):
        return "http://extratorrent.cc/search/?search=" + "+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" ")) + "&new=1&x=0&y=0"

    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing extratorrent page validation for: "+tor)
        lg.debug("\t\tNot Implemented: extratorrent page validation, returning true")
        return True

    def get_torrent_from_validated_page(self, page):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tConverting torrent url to ext format : "+page)
        return "http://extratorrent.cc" + page.replace("torrent_", "")

class IsoHuntSearch(BaseSearch):
    def __init__(self):
        self.name = "isohunt"
        self.delimiter = "+"
        self.can_get_tor_from_main_page = False

    def get_links_from_main_page_re(self):
        return ".*"

    def get_is_link_a_torrent_re(self):
        return ".*tab=summary$"

    def get_search_url(self, name, maskval):
        return "http://isohunt.com/torrents/" + "+".join(name.split(" ")).replace("'","")+"+"+"+".join(maskval.split(" ")) + "?iht=-1&ihp=1&ihs1=1&iho1=d"

    def get_torrent_from_validated_page(self, page):
        turl = "http://www.isohunt.com" + page
        resp = urllib2.urlopen(turl)
        val_page = resp.read()
        val_tags = BeautifulSoup(val_page)
        links = val_tags.findAll('a', href=re.compile("ca.*torrent"))
        for l in links:
            return string.lower(l['href'])
        return ""

    def validate_page(self, tor):
        lg = logging.getLogger('spiderbro')
        lg.debug("\t\tDoing isohunt page validation for: "+tor)
        lg.debug("\t\tNot Implemented: isohunt page validation, returning true")
        return True


def get_configuration():
    """
        read the configuration file, set opts
    """
    # Set up config file
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("--conf_file", help="Specify config file", metavar="FILE", default="/home/gom/code/python/spider_bro/config.ini")
    args, remaining_argv = conf_parser.parse_known_args()
    defaults = {"tv_dir" : "some default",}
    if args.conf_file:
        config = ConfigParser.SafeConfigParser()
        config.read([args.conf_file])
        defaults = dict(config.items("spiderbro"))

    # Don't surpress add_help here so it will handle -h
    parser = argparse.ArgumentParser(parents=[conf_parser], formatter_class=argparse.RawDescriptionHelpFormatter, description='Spiderbro! Spiderbro! Finding episodes for your shows!')
    parser.add_argument('--test',  action="store_true", default=False, help='Don\'t actually download episodes')
    parser.add_argument('--debug_logging',  action="store_true", default=False, help='Turn on Debug Logging')
    parser.add_argument('--xbmc_sqlite_db', type=str, required=False, default="", help='XBMC SQLite DB')
    parser.add_argument('--mysql',  action="store_true", default=True, help='Use Mysql DB')

    parser.add_argument('--host', type=str, required=False, default="", help='Mysql host')
    parser.add_argument('--user', type=str, required=False, default="", help='Mysql user')
    parser.add_argument('--pwd', type=str, required=False, default="", help='Mysql password')
    parser.add_argument('--schema', type=str, required=False, default="", help='MySql schema')

    parser.add_argument('-a', '--all',  action="store_true", default=True, help='Find episodes for all shows')
    parser.add_argument('-cc', '--clear_cache',  action="store_true", default=False, help='Clear the internal SB episode cache for show(s)')
    parser.add_argument('-f', '--use_file_renamer',  action="store_true", default=True, help='Use the file_renamer script after torrent downloads')
    parser.add_argument('-hq', '--high_quality',  action="store_true", default=False, help='Switch show to high quality')
    parser.add_argument('-lq', '--low_quality',  action="store_true", default=False, help='Switch show to low quality')
    parser.add_argument('-l', '--force_learn',  action="store_true", default=False, help='Force SB to mark episode(s) as downloaded')
    parser.add_argument('-p', '--polite',  action="store_true", default=False, help='Wait N seconds before opening each url')
    parser.add_argument('-v', '--verbose',  action="store_true", default=False, help='Verbose output')

    parser.add_argument('-d', '--db_file', type=str, required=False, default='spiderbro.db', help='Spiderbro internal database file')
    parser.add_argument('-ld', '--log_dir', type=str, required=False, default="log", help='Logging Dir')
    parser.add_argument('-pv', '--polite-value', type=int, required=False, default=5, help='Num seconds for polite')
    parser.add_argument('-s', '--show', type=str, required=False, help='Find episodes for a single show')
    parser.add_argument('-t', '--tv_dir', type=str, required=False, default='/home/gom/nas/tv/', help='TV directory')
    parser.add_argument('--force_id', type=str, required=False, help='Force a show to change its id')

    parser.set_defaults(**defaults)
    args = parser.parse_args(remaining_argv)
    if args.show: args.all = False
    return args

#################################################################################################################
# SpiderBro main class
#################################################################################################################
class SpiderBro:
    def __init__(self, opts, episode_masks=None, season_masks=None, ignore_taglist=None, site_search_list=None):
        """
        Set up logger, db_manager, configuration
        """
        if episode_masks is None: episode_masks = []
        if season_masks is None: season_masks = []
        if ignore_taglist is None: ignore_taglist = []
        if site_search_list is None: site_search_list = []
        self.episode_masks = episode_masks
        self.season_masks = season_masks
        self.ignore_taglist = ignore_taglist
        self.site_search_list = site_search_list

        self.config = opts
        self.logger = self.setup_logger()
        self.db = self.setup_db_manager()
        self.download_list = []

    def setup_logger(self):
        """
        Set up all the logging paramters for SpiderBro
        """
        start_day = str(datetime.today()).split(" ")[0]
        setupLogger()
        self.logger = logging.getLogger("spiderbro")
        if (self.config.debug_logging == True):
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
        handler_stream = logging.StreamHandler()
        handler_stream.setFormatter(formatter)
        handler_stream.setLevel(logging.CRITICAL)
        self.logger.addHandler(handler_stream)
        handler_file = logging.FileHandler('%s/spiderBro_%s.log' % (self.config.log_dir, start_day))
        handler_file.setFormatter(formatter)
        self.logger.addHandler(handler_file)
        self.logger.info("")
        self.logger.info("SpiderBro, SpiderBro")
        self.logger.info("Finding episodes for your shows")
        self.log_debug_info()
        return self.logger

    def log_debug_info(self):
        """
            Log some debugging info about configuration
        """
        self.logger.debug("")
        self.logger.debug("Using params:")
        dic = vars(self.config)
        sopts = dic.keys()
        sopts.sort()
        for k in sopts:
            self.logger.debug("%s: %s" % (k, dic[k]))
        self.logger.debug("")

    def setup_db_manager(self):
        """
        Set up the db manager based on a dictionary of options supplied by get_configuration
        """
        db = db_manager()

        if(self.config.db_file):
            db.init_sb_db(self.config.db_file)
        else:
            db.init_sb_db('spiderbro.db')

        if(self.config.mysql):
            db.xbmc_init_mysql(self.config.host, self.config.user, self.config.pwd, self.config.schema) 
        else: 
            db.xbmc_init_sqlite(self.config.xbmc_sqlite_db) 

        if(self.config.clear_cache and self.config.show):
            self.logger.info("Clearing db cache for show %s" % (self.config.show))
            db.clear_cache(self.config.show)
        
        if(self.config.high_quality and self.config.show):
            self.logger.info("Changing quality to high for show %s" % (self.config.show))
            db.set_quality(self.config.show, 1)
        
        if(self.config.low_quality and self.config.show):
            self.logger.info("Changing quality to low for show %s" % (self.config.show))
            db.set_quality(self.config.show, 0)
        
        if(self.config.force_id and self.config.show):
            self.logger.info("Forcing new id %s for show %s" % (self.config.force_id, self.config.show))
            db.update_series_id(self.config.show, self.config.force_id)
        return db
    

    def get_series_id(self, series_name):
        """
        Get the tvdb.com series id for a given tv show
        """
        
        xbmc_id = self.db.xbmc_get_series_id(series_name)
        sb_id = self.db.get_show_info(series_name)

        # Edge case can happen here where show in xbmc but not in sb_db, so we make sure it is inserted
        if(xbmc_id and not sb_id):
            self.logger.debug("No db entry found for show %s, creating default..." % series_name)
            self.db.add_show(xbmc_id[0][0], series_name, 0)

        # try and get series id from xbmc db first if force_id not True
        if(xbmc_id and not ('force_id' in self.config)):
            self.logger.debug("\t\tGot series ID from XBMC: %s" % xbmc_id[0][0])
            return xbmc_id[0][0]

        # otherwise go to sb_db
        if sb_id:
            sid = sb_id[0][0]
            self.logger.debug("\t\tGot series ID from Spiderbro Internal DB: %s" % sid)
            return sid
        # finally go to tvdb if all other options exhausted
        else:
            try:
                page = urllib2.urlopen("http://thetvdb.com/api/GetSeries.php?seriesname=%s" % urllib2.quote(series_name))
                soup = BeautifulSoup(page)
                sid = int(soup.data.series.seriesid.string)
                self.logger.debug("\t\tGot series ID from tvdb: %s" % sid)
                self.db.add_show(sid, series_name, 0)
                return sid
            except Exception, e:
                self.logger.error("Error retrieving series id: %s" % e)


    def get_episode_list(self, series_name):
        """
        Return tuple:
            (list) the list of episodes to be downloaded for a show, if any
            (boolean) has_show_ended
            (int) highest season in show
        """
        aired_list = []
        have_list = []
        highest_season = 1
        ended = False
        self.logger.info("Looking for eps for: %s" % (series_name))
        # get the series id from db or web
        series_id = self.get_series_id(series_name)
        try:

            self.logger.debug("Using thetvdb ID: %s" % (series_id))
            # now get the info for the series
            data = BeautifulSoup(urllib2.urlopen("http://thetvdb.com/data/series/%s/all/" % str(series_id))).data
            if(data.series.status.string == "Ended"):
                ended = True

            # iterate through data, get list of season/episodes for show starting from 1 (0 are specials)
            for i in data.findAll('episode', recursive=False):
                if(i.seasonnumber.string != '0'):
                    season = i.seasonnumber.string
                    ep = i.episodenumber.string
                    try:
                        fa = i.firstaired.string.split('-')
                        airdate = date(int(fa[0]), int(fa[1]), int(fa[2]))
                        # need to compare current date to air date, ignore if not aired yet
                        if date.today() > airdate:
                            aired_list.append((season, ep))
                            highest_season = max(highest_season, int(i.seasonnumber.string))
                    except:
                        pass
        except:
            self.logger.error("\tCould not get episode list from thetvdb (timeout or invalid ID? Using ID: %s)" % (series_id))
            self.logger.error("")
            return [], False, highest_season

        try:
            # use the mysql lib to access xbmc db, cross check episode lists
            l = self.db.xbmc_get_eps_for_show(series_name)
            for i in l: have_list.append(i)

            # create new db con to torrents db, populate from here aswell
            l = self.db.get_eps_from_self(series_name)
            for s, e in l: have_list.append((str(s), str(e)))

        except ValueError as v:
            self.logger.error("Database error?")
            self.logger.error(str(v))
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

    def normalize_series_name(self, name):
        """
        Return the tv show name stripped of any special characters, spaces replaced with _ and all in lower case
        """
        normalized_showname = str(name)
        normalized_showname = str.lower(normalized_showname)
        normalized_showname = normalized_showname.replace("::", "")
        normalized_showname = normalized_showname.replace(": ", " ")
        normalized_showname = normalized_showname.replace(":", " ")
        normalized_showname = "".join(ch for ch in normalized_showname if ch not in ["!", "'", ":", "(", ")", ".", ","])
        normalized_showname = normalized_showname.replace("&", "and")
        normalized_showname = normalized_showname.replace(" ", "_") 
        return normalized_showname
    
    def hunt_eps(self, series_name):
        """
        Find episodes on various torrent sites for some show
        """
        normalized_showname = self.normalize_series_name(series_name)
        dir = self.config.tv_dir + normalized_showname
        
        is_high_quality = self.db.get_show_high_quality(series_name)

        ep_list, ended, highest_season = self.get_episode_list(series_name)

        if ended and not ep_list:
            self.logger.info("\tGot all episodes for this, skipping in future")
            self.db.mark_show_finished(series_name)
        elif ep_list:
            # search for sX eX using every search site and every filemask until torrent is found
            for s, e in ep_list:
                found = False
                # if searching for full season season use season mask list
                if(e == "-1"):
                    self.logger.info("Searching for entire season %s of %s" % (s, series_name))
                    masks_list = self.season_masks
                else:
                    masks_list = self.episode_masks
                for torrent_site_searcher_class in self.site_search_list:
                    if not found:
                        for mk_ctor in masks_list:
                            if self.config.polite: time.sleep(self.config.polite_value)
                            site = torrent_site_searcher_class()
                            try:
                                url = site.search(series_name, s, e, mk_ctor, self.ignore_taglist, is_high_quality)
                                if url:
                                    self.logger.info("\t\tFound torrent: %s" % url)
                                    save_dir = dir
                                    if(self.config.use_file_renamer):
                                        save_dir = dir + "s" + s + "e" + e
                                    dict = {'url':url, "save_dir":save_dir, 'showname':series_name, "season":s, "episode":e}
                                    self.download_list.append(dict)
                                    found = True
                                    break
                            except AttributeError as ex:
                                self.logger.error("%s timed out?" % ex)
                            except Exception, e:
                                self.logger.error("Error: %s" % e)
                                traceback.print_exc()
                                #sys.exit()
                if not found:
                    #check episode is not in current season, do not search again if so
                    ep_season = int(s)
                    # something goes weird here; self.config.force_learn always evaluates as True using 'or self.config.force_learn' - why?
                    if ((ep_season < highest_season) or ended or self.config.force_learn == True):
                        self.logger.info("Cannot find torrent for: %s season %s episode %s - skipping this in future" % (series_name, s, e))
                        self.db.add_to_urls_seen(series_name, s, e, "None", "None")
                self.logger.info("")

    def get_torrent_download_list(self):
        """
        Searches for episodes of shows, populates spiderBros internal list of shows/urls to get
        """
        ignore_list = self.db.get_ignore_list()

        if(self.config.all):
            # if ALL, we get the complete list of shows from xbmc, minus the finished shows (if any)
            self.logger.info("Scanning entire XBMC library, this could take some time...")
            full_showlist = []
            db_showlist = self.db.xbmc_get_showlist()
            for show in db_showlist:
                if(show[0].decode('latin-1', 'replace') not in ignore_list): full_showlist.append(show[0])
            #TODO: add this to config file
            get_trakt_watch_list = True
            if(get_trakt_watch_list):
                self.logger.info("Looking for shows from trakt.com watchlist")
                # get the watchlist from trakt and add
                traktlist = traktWatchlistScraper("thegom145", "b837e9f111dcae8e279711ce929e9ef1")
                full_showlist.extend(t for t in traktlist if t.decode('latin-1', 'replace') not in ignore_list and t not in full_showlist)
                full_showlist.sort()
            for show in full_showlist:
                if(show.decode('latin-1', 'replace') not in ignore_list):
                    self.hunt_eps(show)

        else:
            # if SHOW, get specified show
            if(self.config.show):
                self.hunt_eps(self.config.show)
            
            # else EXIT
            else:
                self.logger.info("No shows to download, exiting")

        return self.download_list

def traktWatchlistScraper(username, key):
    """
        returns a list of shows from the watchlist of a trakt user
    """
    watchlist = []
    try:
        l = logging.getLogger("spiderbro")
        url = "http://api.trakt.tv/user/watchlist/shows.json/"+ key +"/" + username
        response = urllib2.urlopen(url)
        data = json.load(response)
        watchlist = [i["title"] for i in data]
        l.debug("Got list of watched shows from trakt.com:")
        for show in watchlist: l.debug(show)
    except:
        pass
