"""
OMOP CDM utility functions
"""

import argparse
import logging

import bq_utils
import common
import resources

logger = logging.getLogger(__name__)


def tables_to_map():
    """
    Determine which CDM tables must have ids remapped

    :return: the list of table names
    """
    result = []
    for table in resources.CDM_TABLES:
        if table != 'person' and bq_utils.has_primary_key(table):
            result.append(table)
    return result


def create_table(table, dataset_id):
    """
    Create OMOP table in the specified dataset

    :param table: CDM table to generate
    :param dataset_id: identifies the dataset to create the tables in
    :return:
    """
    logger.info('Creating table {dataset_id}.{table}...'.format(table=table, dataset_id=dataset_id))
    bq_utils.create_standard_table(table, table, drop_existing=True, dataset_id=dataset_id)


def create_vocabulary_tables(dataset_id):
    """
    Create OMOP vocabulary tables in the specified dataset
    :param dataset_id:
    :return:
    """
    logger.info('Creating vocabulary tables in {dataset_id}...'.format(dataset_id=dataset_id))
    for table in common.VOCABULARY_TABLES:
        create_table(table, dataset_id)


def create_all_tables(dataset_id):
    """
    Create all the OMOP clinical data tables in the specified dataset

    :param dataset_id: identifies the dataset to create the tables in
    :return:
    """
    logger.info('Creating all CDM tables in {dataset_id}...'.format(dataset_id=dataset_id))
    for table in resources.CDM_TABLES:
        create_table(table, dataset_id)


if __name__ == '__main__':
    # TODO parse args, support multiple commands
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--table',
                        help='A specific CDM table to create (creates all by default)',
                        choices=list(resources.CDM_TABLES))
    parser.add_argument('--component',
                        help='Subset of CDM tables to create',
                        choices=list(common.CDM_COMPONENTS))
    parser.add_argument('dataset_id',
                        help='Identifies the dataset to create OMOP table(s) in')
    args = parser.parse_args()
    if args.table:
        if args.component:
            raise RuntimeError('Cannot process both table and component')
        create_table(args.table, args.dataset_id)
    elif args.component:
        if args.component == common.VOCABULARY:
            create_vocabulary_tables(args.dataset_id)
        elif args.component == common.ACHILLES:
            # TODO implement creating achilles tables; need to fix interdependency of common, resources, cdm
            raise NotImplementedError('Creating achilles tables not yet implemented')
    else:
        create_all_tables(args.dataset_id)
