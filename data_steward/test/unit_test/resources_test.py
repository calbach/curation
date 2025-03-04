import unittest

import common
import resources


class ResourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print('**************************************************************')
        print(cls.__name__)
        print('**************************************************************')

    def test_cdm_csv(self):
        cdm_data_rows = resources.cdm_csv()
        expected_keys = {'table_name', 'column_name', 'is_nullable', 'data_type', 'description'}
        expected_table_names = {'person', 'visit_occurrence', 'condition_occurrence', 'procedure_occurrence',
                                'drug_exposure', 'measurement'}
        actual_table_names = set()
        for row in cdm_data_rows:
            keys = set(row.keys())
            self.assertSetEqual(expected_keys, keys)
            actual_table_names.add(row['table_name'])

        for expected_table_name in expected_table_names:
            self.assertIn(expected_table_name, actual_table_names)

    def test_cdm_schemas(self):
        schemas = resources.cdm_schemas()
        table_names = schemas.keys()

        result_internal_tables = [table_name for table_name in table_names if resources.is_internal_table(table_name)]
        self.assertCountEqual([], result_internal_tables,
                             msg='Internal tables %s should not be in result of cdm_schemas()' % result_internal_tables)

        achilles_tables = common.ACHILLES_TABLES + common.ACHILLES_HEEL_TABLES
        result_achilles_tables = [table_name for table_name in table_names if table_name in achilles_tables]
        self.assertCountEqual([], result_achilles_tables,
                             msg='Achilles tables %s should not be in result of cdm_schemas()' % result_achilles_tables)

        result_vocab_tables = [table_name for table_name in table_names if table_name in resources.VOCABULARY_TABLES]
        self.assertCountEqual([], result_vocab_tables,
                             msg='Vocabulary tables %s should not be in result of cdm_schemas()' % result_vocab_tables)

    def tearDown(self):
        super(ResourcesTest, self).tearDown()
