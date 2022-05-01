import argparse
import json
import logging
import os
import sys

from ffq.utils import findkey

from . import __version__
from .ffq import (
    ffq_doi, ffq_gse, ffq_run, ffq_study, ffq_sample, ffq_gsm, ffq_experiment,
    ffq_encode, ffq_bioproject, ffq_biosample, validate_accessions
)

logger = logging.getLogger(__name__)

RUN_TYPES = (
    'SRR',
    'ERR',
    'DRR',
)
PROJECT_TYPES = (
    'SRP',
    'ERP',
    'DRP',
)
EXPERIMENT_TYPES = (
    'SRX',
    'ERX',
    'DRX',
)
SAMPLE_TYPES = ('SRS', 'ERS', 'DRS', 'CRS')
GEO_TYPES = ('GSE', 'GSM')
ENCODE_TYPES = ('ENCSR', 'ENCBS', 'ENCDO')
BIOPROJECT_TYPES = (
    'CRX',
)  # TODO implement CRR and CRP, most dont have public metadata.
BIOSAMPLE_TYPES = ('SAMN', 'SAMD', 'SAMEA', 'SAMEG')
OTHER_TYPES = ('DOI',)
SEARCH_TYPES = RUN_TYPES + PROJECT_TYPES + EXPERIMENT_TYPES + SAMPLE_TYPES + \
    GEO_TYPES + ENCODE_TYPES + BIOPROJECT_TYPES + BIOSAMPLE_TYPES + OTHER_TYPES

# main ffq caller
FFQ = {
    "DOI": ffq_doi,
    "GSM": ffq_gsm,
    "GSE": ffq_gse,
}
FFQ.update({t: ffq_run for t in RUN_TYPES})
FFQ.update({t: ffq_study for t in PROJECT_TYPES})
FFQ.update({t: ffq_experiment for t in EXPERIMENT_TYPES})
FFQ.update({t: ffq_sample for t in SAMPLE_TYPES})
FFQ.update({t: ffq_encode for t in ENCODE_TYPES})
FFQ.update({t: ffq_bioproject for t in BIOPROJECT_TYPES})
FFQ.update({t: ffq_biosample for t in BIOSAMPLE_TYPES})


def main():
    """Command-line entrypoint.
    """
    # Main parser
    parser = argparse.ArgumentParser(
        description=((
            f'ffq {__version__}: A command line tool to find sequencing data '
            'from SRA / GEO / ENCODE / ENA / EBI-EMBL / DDBJ / Biosample.'
        ))
    )
    parser._actions[0].help = parser._actions[0].help.capitalize()

    parser.add_argument(
        'IDs',
        help=(
            'One or multiple SRA / GEO / ENCODE / ENA / EBI-EMBL / DDBJ / Biosample accessions, '
            'DOIs, or paper titles'
        ),
        nargs='+'
    )
    parser.add_argument(
        '-o',
        metavar='OUT',
        help=('Path to write metadata (default: standard out)'),
        type=str,
        required=False,
    )

    parser.add_argument(
        '-t',
        metavar='TYPE',
        help=argparse.SUPPRESS,
        type=str,
        required=False,
        choices=SEARCH_TYPES
    )

    parser.add_argument(
        '-l',
        metavar='LEVEL',
        help='Max depth to fetch data within accession tree',
        type=int
    )

    parser.add_argument('--ftp', help='Return FTP links', action='store_true')

    parser.add_argument(
        '--aws',
        help=  # noqa
        'Return AWS links',
        action='store_true'
    )

    parser.add_argument(
        '--gcp',
        help=  # noqa
        'Return GCP links',
        action='store_true'
    )

    parser.add_argument(
        '--ncbi',
        help=  # noqa
        'Return NCBI links',
        action='store_true'
    )
    parser.add_argument(
        '--split',
        help=  # noqa
        'Split output into separate files by accession  (`-o` is a directory)',
        action='store_true'
    )
    parser.add_argument(
        '--verbose', help='Print debugging information', action='store_true'
    )

    # Show help when no arguments are given
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    logging.basicConfig(
        format='[%(asctime)s] %(levelname)7s %(message)s',
        level=logging.DEBUG if args.verbose else logging.INFO,
    )
    logging.getLogger('chardet.charsetprober').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    logger.debug('Printing verbose output')
    logger.debug(args)

    # Check the -o is provided if --split is set
    if args.split and not args.o:
        parser.error('`-o` must be provided when using `--split`')

    if args.l:
        if args.l <= 0:  # noqa
            parser.error('level `-l` must be equal or greater than 1')
    if args.t:
        if args.t not in SEARCH_TYPES:
            parser.error(
                f"{args.t} is not a valide type. TYPES can be one of {', '.join(SEARCH_TYPES)}"
            )

    # "clean" the provided ids
    accessions = validate_accessions(args.IDs, SEARCH_TYPES)

    # check if accessions are valid (TODO separate cleaning accessions and checking them)
    for v in accessions:
        if v["valid"] is False:
            parser.error(
                f"{v['accession']} is not a valid ID. IDs can be one of {', '.join(SEARCH_TYPES)}"  # noqa
            )
            sys.exit(1)

    # we want to associate the args.x with the name of X
    # not just the true/false associated with args.x
    link_args = [{
        "link_type": "ftp",
        "arg": args.ftp
    }, {
        "link_type": "aws",
        "arg": args.aws
    }, {
        "link_type": "gcp",
        "arg": args.gcp
    }, {
        "link_type": "ncbi",
        "arg": args.ncbi
    }]

    # Run FFQ based on type and accessions
    keyed = {}
    try:
        # standard ffq
        results = [FFQ[v["prefix"]](v["accession"], args.l) for v in accessions]
        keyed = {result['accession']: result for result in results}

        # get links ffq
        if [v["arg"] for v in link_args].count(True) > 0:
            links = []
            for v in link_args:
                if v["arg"]:
                    found_links = []
                    findkey(keyed, v["link_type"], found_links)
                    for obj in found_links:
                        # for each link add the source
                        obj["linktype"] = v["link_type"]
                        links.append(obj)

            keyed = links

    except Exception as e:
        if args.verbose:
            logger.exception(e)
        else:
            logger.error(e)

    if args.o:
        if args.split:
            # Split each result into its own JSON.
            for result in keyed:
                os.makedirs(args.o, exist_ok=True)
                with open(os.path.join(args.o, f'{result["accession"]}.json'),
                          'w') as f:
                    json.dump(result, f, indent=4)
        else:
            # Otherwise, write a single JSON with result accession as keys.
            if os.path.dirname(
                    args.o) != '':  # handles case where file is in current dir
                os.makedirs(os.path.dirname(args.o), exist_ok=True)
            with open(args.o, 'w') as f:
                json.dump(keyed, f, indent=4)
    else:
        print(json.dumps(keyed, indent=4))
