#!/usr/bin/env python3

import sys
import argparse
import requests
import utils
from bs4 import BeautifulSoup

def check_args_SRR(SRR):
    if SRR[0:3] != "SRR":
        sys.stderr.write("[Error] Not a valid SRR number, must begin with 'SRR'\n")
        return False
    if len(SRR) != 10:
        sys.stderr.write("[Error] SRR number must be 10 digits long\n")
        return False
    if not SRR[3:].isdigit():
        sys.stderr.write("[Error] Not a valid SRR number, must end in digits\n")
        return False
    return True

def check_args(args):
    ## SRR
    for sn, s in enumerate(args.SRR):
        if not check_args_SRR(s):
            return False
    return True

def get_page(url):
    page = requests.get(url)
    return page
def get_soup(page):
    soup = BeautifulSoup(page.text, "xml")
    return soup

# try this: https://www.ebi.ac.uk/ena/data/warehouse/filereport?accession=SRR8426372&result=read_run&fields=run_accession,fastq_ftp

def single(SRR):
    base_url = "https://www.ebi.ac.uk/ena/browser/api/xml/"
    url = base_url + SRR
    soup = get_soup(get_page(url))

    ftp = utils.get_ftp_links(soup)
    title = utils.get_title(soup)

    # source_link = "https://www.ebi.ac.uk/ena/data/warehouse/filereport?accession={}&result=read_run&fields=run_accession,fastq_ftp".format(SRR)

    for f in ftp:
        sys.stdout.write("{}\t{}\t{}\n".format(SRR, "\t".join(title), f))

def multiple(units):
    # Looping is naive implementatino
    # xml api can take multiple SRR's as string
    for sn, s in enumerate(units):
        single(s)
    return True

def ffq(args):
    if not check_args(args): return False

    units = args.SRR
    #base = "https://www.ebi.ac.uk/ena/browser/api/xml/"
    multiple(units)

    return True