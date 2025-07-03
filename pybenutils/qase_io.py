import json
import os
from typing import Union

from qase.api_client_v1 import Configuration, ApiClient, ApiException, CasesApi

from pybenutils.cli_tools import cli_main_for_class
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


class QaseIO:
    def __init__(self, project_code: str, qase_token:str, qase_pytest_api_key: str):
        self.project_code = project_code if project_code else os.environ.get('QASE_PROJECT_CODE', '')
        self.qase_pytest_api_key = qase_pytest_api_key if qase_pytest_api_key else os.environ.get('QASE_PYTEST_API_KEY', '')
        self.configuration = Configuration(host='https://api.qase.io/v1')
        self.configuration.api_key['TokenAuth'] = qase_token if qase_token else os.environ.get('QASE_TOKEN', '')

    class QaseConfig:
        config_file_name = 'qase.config.json'

        def __init__(self, project_code: str, qase_pytest_api_key: str):
            self.project_code = project_code
            self.qase_pytest_api_key = qase_pytest_api_key

            qase_default_config = {
                "mode": "testops",
                "fallback": "report",
                "report": {
                    "driver": "local",
                    "connection": {
                        "local": {
                            "path": "./build/qase-report",
                            "format": "json"
                        }
                    }
                },
                "testops": {
                    "project": self.project_code,
                    "api": {
                        "token": self.qase_pytest_api_key,
                        "host": "qase.io"
                    },
                    "run": {
                        "complete": False
                    },
                    "defect": False,
                    "bulk": True,
                    "chunk": 200
                },
                "framework": {
                    "pytest": {
                        "capture": {
                            "logs": True,
                            "http": True
                        }
                    }
                },
                "environment": "local"
            }

            if os.path.exists('qase.config.json'):
                self.read()
            else:
                self.config_obj = qase_default_config

        def write(self):
            with open(self.config_file_name, 'w') as f:
                json.dump(self.config_obj, f)

        def read(self):
            with open(self.config_file_name, 'r') as f:
                self.config_obj = json.load(f)

        def remove(self):
            full_path = os.path.join(os.getcwd(), self.config_file_name)
            if os.path.exists(full_path):
                os.remove(full_path)

        def add_run_id(self, run_id: Union[int, str]):
            self.config_obj['testops']['run']['id'] = int(run_id)
            self.config_obj['testops']['run'].pop('title', '')
            self.config_obj['testops']['run']['complete'] = False
            self.write()

        def add_run_title(self, run_title: str):
            self.config_obj['testops']['run']['title'] = run_title
            self.config_obj['testops']['run'].pop('id', '')
            self.config_obj['testops']['run']['complete'] = True
            self.write()

        def complete_run(self):
            self.config_obj['testops']['run']['complete'] = True
            self.write()

        def dont_complete_run(self):
            self.config_obj['testops']['run']['complete'] = False
            self.write()

    def get_test_case(self, case_id:int):
        """Returns the test case details

        :param case_id: An int representing the Qase test case id taken from the test case name.
        :return: The Qase API result dict with a 'status' key containing a boolean.
        """
        assert case_id, 'case_id is required'
        with ApiClient(self.configuration) as api_client:
            api_instance = CasesApi(api_client)
            try:
                return api_instance.get_case(self.project_code, case_id)
            except ApiException as ex:
                logger.error(f'Exception while trying to get Qase test case "{case_id}": {ex}')

if __name__ == '__main__':
    cli_main_for_class(QaseIO)