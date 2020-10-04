import boto3
import datetime
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


class AmazonEC2Obj:
    def __init__(self, aws_access_key_id, aws_secret_access_key, region_name, dalek_mode=False):
        """Amazon EC2 Object declaration

        :param aws_access_key_id: AWS access key id
        :param aws_secret_access_key: AWS secret access key
        :param region_name: AWS region to connect too
        :param dalek_mode: Debug mode (dr who reference)
        """
        self.ec2 = boto3.client('ec2',
                                region_name=region_name,
                                aws_access_key_id=aws_access_key_id,
                                aws_secret_access_key=aws_secret_access_key
                                )
        self.dalek_mode = dalek_mode
        if self.dalek_mode:
            logger.debug('EC2 is connected, I demand orders!')

    def get_instances(self, search_filter_dict):
        """Returns an ec2 collection object containing all the ec2 instances matching the search dict

        :param search_filter_dict: Dict of key:[value] to filter the ec2 instances search
        :return: Ec2 instances collection obj
        """
        filters_list = [{'Name': key, 'Values': value} for key, value in search_filter_dict.items()]
        if self.dalek_mode:
            logger.debug('Filtering by: {filter}'.format(filter=filters_list))
        response = self.ec2.describe_instances(Filters=filters_list)
        instances_list = []
        for reservation in (response["Reservations"]):
            instances_list += reservation["Instances"]
        return instances_list

    def terminate_instances_by_id(self, instances_ids_list):
        """Terminates an instance by ID list

        :param instances_ids_list: An EC2 instances id list
        :return: True if successful
        """
        returned_result_dict = {'success': True, 'terminated_instances_ids': [], 'error_ids': []}
        remained_instances_ids_to_terminate = instances_ids_list
        try:
            terminated_instances_dict = self.ec2.terminate_instances(InstanceIds=remained_instances_ids_to_terminate)

            terminated_instances_ids = [x['InstanceId'] for x in terminated_instances_dict['TerminatingInstances']]
            print('Following instances ids were terminated: {inst_ids}'.format(inst_ids=terminated_instances_ids))
            if terminated_instances_ids:
                returned_result_dict['terminated_instances_ids'].extend(terminated_instances_ids)

            remained_instances_ids_to_terminate = [n for n in remained_instances_ids_to_terminate
                                                   if n not in terminated_instances_ids]
            if remained_instances_ids_to_terminate:
                raise Exception('Following instances Ids failed to be terminated: "{inst_ids}"'.
                                format(inst_ids=remained_instances_ids_to_terminate))
        except Exception as e:
            print(str(e))
            print('Exception while trying terminated list of instances ids. Will try terminated one by one')

            for instance_id in remained_instances_ids_to_terminate:
                try:
                    terminated_instances_dict = self.ec2.terminate_instances(
                        InstanceIds=[instance_id])
                    terminated_instances_ids = [x['InstanceId'] for x in
                                                terminated_instances_dict['TerminatingInstances']]
                    print('instance id "{inst_id}" terminated'.format(inst_id=terminated_instances_ids))

                    returned_result_dict['terminated_instances_ids'].append(instance_id)
                except Exception as e:
                    returned_result_dict['success'] = False
                    print('Exception while trying to terminate instance id: "{inst_id}. Exception is: "{exp}"'.format(
                        inst_id=instance_id, exp=str(e)))
                    returned_result_dict['error_ids'].append({'id': instance_id, 'error': str(e)})

        return returned_result_dict

    def terminate_instance_by_name(self, instance_name):
        """Terminates an instance by it's Name tag

        :param instance_name:
        :return: True if successful
        """
        if not instance_name:
            logger.error('ABORTING: I do not permit the deletion of an empty Name tag search')
            return False
        id_list = self.get_instance_ids_by_name(instance_name)
        if id_list:
            self.terminate_instances_by_id(id_list)
        else:
            logger.error('ABORTING: The id list for the given name is empty')
            if self.dalek_mode:
                logger.debug('EXPLAIN! EXPLAIN!')
            return False
        return True

    def terminate_old_instances(self, minutes_to_keep_instances=1440, terminate_running_instances=False,
                                excluded_tags=None):
        """Search and terminate "stopped" instances that are older than the given int in seconds

        :param minutes_to_keep_instances: The number (int) of minutes to keep an instance
        :param terminate_running_instances: True: running & stopped instances. False: only stopped instances.
        :param excluded_tags: List of excluded tags. Any machine tagged with one of these tags will not be terminated.
        :return: True if successful
        """
        instances_state_filter = ['stopped', 'running'] if terminate_running_instances else ['stopped']
        search_filter_dict = {'instance-state-name': instances_state_filter}
        instances_list = self.get_instances(search_filter_dict)

        uid_list_for_deletion = []
        script_time = datetime.datetime.utcnow()
        seconds_to_keep_instances = minutes_to_keep_instances * 60
        for instance in instances_list:
            if excluded_tags and any(
                    item in excluded_tags for item in [tag['Key'] for tag in instance.get('Tags', [])]):
                continue
            time_diff = script_time - instance['LaunchTime'].replace(tzinfo=None)
            time_diff_in_seconds = time_diff.days * 86400 + time_diff.seconds
            if time_diff_in_seconds >= seconds_to_keep_instances and not self.verify_termination_protection(
                    instance['InstanceId']):
                uid_list_for_deletion.append(instance['InstanceId'])
        return self.terminate_instances_by_id(instances_ids_list=uid_list_for_deletion)

    def get_instance_ids_by_name(self, instance_name):
        """Get instances id list by an instance Name tag

        :param instance_name: An instance Name tag value to search
        :return: Instances id list
        """
        search_filter_dict = {'tag:Name': [instance_name]}
        instances_list = self.get_instances(search_filter_dict)
        instance_id_list = []
        for instance in instances_list:
            instance_id_list.append(instance['InstanceId'])
            logger.debug('ID:{id}, Name:{name}'.format(id=instance['InstanceId'], name=instance_name))
        return instance_id_list

    def verify_termination_protection(self, instance_id):
        """Returns the termination protection attribute value

        :param instance_id: The instance id
        :return: Termination protection value
        """
        attribute_dict = self.ec2.describe_instance_attribute(Attribute='disableApiTermination', InstanceId=instance_id)
        return attribute_dict['DisableApiTermination']['Value']
