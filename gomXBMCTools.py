#! /usr/bin/env python
import unicodedata
import unittest
import re

def normaliseTVShowName(series_name):
    """ 
    Uses normalization rules to change string to lowercased with _ instead of space
    and removes characters that are problematic for shell/dirnames
    """
    series_name = str.lower(series_name)
    series_name = series_name.replace("::", "")
    series_name = series_name.replace(": ", " ")
    series_name = series_name.replace(":", " ")
    series_name = series_name.replace(";", " ")
    series_name = series_name.replace("&", "and")
    series_name = series_name.replace(" ", "_") 
    series_name = series_name.replace("/", "_") 
    series_name = series_name.replace("\\", "_") 
    series_name = series_name.replace("_-_", "_") 
    series_name = "".join(ch for ch in series_name if ch not in ["!", "'", ":", "(", ")", ".", ",", "-"])
    # unicode screws up some shows, convert to latin-1 ascii
    series_name = unicode(series_name, "latin-1")
    unicodedata.normalize('NFKD', series_name).encode('ascii','ignore')
    return series_name

def getTorrentNameFromMagnetLink(torrent):
    tor = re.sub("&tr.*$", "", torrent)
    tor = re.sub("magnet.*=", "", tor)
    return tor

def getEpisodeNumFromFilename(file, s):
    """ 
    getEpisodeNumFromFilename(file): parse filename, return episode number
    """ 
    sNeN = re.compile(".*s01e([0-9][0-9]).*")
    gr = sNeN.findall(file)
    try:
        if(gr[0]):
            return "e"+str(gr[0])
    except:
        pass
    

    return "e-1"

def formatNoAsStr(no):
    """ 
    formatSeasonOrEpNo(): pad a zero if no < 10, else do nothing
    """
    return "0" + str(no) if(int(no)<10) else str(no)

class testFunctions(unittest.TestCase):

    def setUp(self):
        self.shows = { "Adam And Joe Go Tokyo":"adam_and_joe_go_tokyo",
            "American Dad!":"american_dad",
            "Archer (2009)":"archer_2009",
            "Avatar: The Last Airbender":"avatar_the_last_airbender",
            "Berry & Fulcher's Snuff Box":"berry_and_fulchers_snuff_box",
            "Charlie Brooker's Screenwipe":"charlie_brookers_screenwipe",
            "Eastbound & Down":"eastbound_and_down",
            "Lucy, The Daughter of the Devil":"lucy_the_daughter_of_the_devil",
            "Penn & Teller: Bullshit!":"penn_and_teller_bullshit",
            "Penn & Teller: Fool Us":"penn_and_teller_fool_us",
            "Star Wars - The Clone Wars":"star_wars_the_clone_wars",
            "Beavis and Butt-Head":"beavis_and_butthead",
            "Don't Trust the B---- in Apartment 23":"dont_trust_the_b_in_apartment_23",
            "Louis Theroux - Extreme Love":"louis_theroux_extreme_love",
            "NTSF:SD:SUV::":"ntsf_sd_suv",
            "The Venture Bros.":"the_venture_bros",
            "Steins;Gate":"steins_gate",
            "Love/Hate":"love_hate"
        }

    def test_normalise(self):
        for k,v in self.shows.items():
           #print normaliseTVShowName(k), " <-> ", v
           self.assertEqual(normaliseTVShowName(k), v)

if __name__ == "__main__":
    # unit tests
    suite = unittest.TestLoader().loadTestsFromTestCase(testFunctions)
    unittest.TextTestRunner(verbosity=2).run(suite)

