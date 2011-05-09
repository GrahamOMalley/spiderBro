#! /usr/bin/env python

import string
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
