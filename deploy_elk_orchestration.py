#!/usr/bin/python

import boto.datapipeline
import boto.ec2.cloudwatch
import boto.iam
import boto.s3
import ConfigParser
import ast
import os
import re
config = ConfigParser.ConfigParser()
config.read('deploy_elk_orchestration.cfg')

# Updates the IAM Role with Permission and Trust Policies
def update_iam_role(iam, role_name, assume_role_policy_file, permission_policy_file) :

  try :
    iam.get_role(role_name)
  except:
    print role_name  + ' role not found. Creating role '
    iam.create_role(role_name)

  print 'Updating assume role policy of ' + role_name
  with open (assume_role_policy_file, "r") as myfile:
    policy=myfile.read()
  iam.update_assume_role_policy(role_name, policy)

  print 'Updating attached permission policies of ' + role_name
  for rp in iam.list_role_policies(role_name) \
               .get('list_role_policies_response') \
               .get('list_role_policies_result').get('policy_names') :
    iam.delete_role_policy(role_name, rp)
  with open (permission_policy_file, "r") as myfile:
    policy=myfile.read()
  iam.put_role_policy(role_name, role_name + '_permission_policy', policy)

  try :
    iam.get_instance_profile(role_name)
  except :
    print role_name  + ' instance profile not found. Creating instance profile'
    iam.create_instance_profile(role_name)
  print 'Updating role and instance profile association of ' + role_name
  for ip in iam.list_instance_profiles_for_role(role_name) \
               .get('list_instance_profiles_for_role_response') \
               .get('list_instance_profiles_for_role_result').get('instance_profiles') :
    iam.remove_role_from_instance_profile(role_name, role_name)
  iam.add_role_to_instance_profile(role_name, role_name)


# Prepare needed IAM roles
def define_iam_roles() :
  print '------------------------------'
  print 'Preparing ELK IAM Roles'
  print '------------------------------'
   
  # Connect to AWS IAM
  iam = boto.iam.connect_to_region(region_name=config.get('general','aws_region'), 
                                   aws_access_key_id=config.get('general','aws_access_key_id'), 
                                   aws_secret_access_key=config.get('general','aws_secret_access_key'))

  # Prepare Data Pipeline Roles
  update_iam_role(iam, config.get('data_pipeline','pipeline_role'), 
                  'iam_policies/datapipeline_role_trust', 'iam_policies/datapipeline_role_policy')
  update_iam_role(iam,  config.get('data_pipeline', 'pipeline_resource_role'), 
                  'iam_policies/datapipeline_resource_role_trust', 'iam_policies/datapipeline_resource_role_policy')
  print 'Successfully prepared IAM roles'


# Upload the custom script to s3
def upload_custom_script(filename) :
  f1 = open('custom_scripts/' + filename, 'r') 
  f2 = open('temp/' + filename, 'w')
  for line in f1:
    # Plug in values
    line = re.sub(r"^.*'--region'.*$", 
                  r"parser.add_argument('-r', '--region', default='" + \
                  config.get('general','aws_region') + "',", line)
    line = re.sub(r"^.*'--logstash_metric_namespace'.*$",
                  r"parser.add_argument('-ln', '--logstash_metric_namespace', default='" + \
                  config.get('cloudwatch', 'logstash_buffer_metric_namespace') + "',", line) 
    line = re.sub(r"^.*'--logstash_metric_name'.*$",
                  r"parser.add_argument('-lm', '--logstash_metric_name', default='" + \
                  config.get('cloudwatch', 'logstash_buffer_metric_name') + "',", line)
    line = re.sub(r"^.*'--indexer_opsworks_layer_id'.*$",
                  r"parser.add_argument('-i', '--indexer_opsworks_layer_id', default='" + \
                  config.get('opsworks', 'indexer_opsworks_layer_id') + "',", line)
    line = re.sub(r"^.*'--shipper_opsworks_layer_id'.*$",
                  r"parser.add_argument('-s', '--shipper_opsworks_layer_id', default='" + \
                  config.get('opsworks', 'shipper_opsworks_layer_id') + "',", line)
    line = re.sub(r"^.*'--redis_opsworks_layer_id'.*$",
                  r"parser.add_argument('-e', '--redis_opsworks_layer_id', default='" + \
                  config.get('opsworks', 'redis_opsworks_layer_id') + "',", line)
    line = re.sub(r"^.*'--source_s3_bucket'.*$",
                  r"parser.add_argument('-sb', '--source_s3_bucket', default='" + \
                  config.get('custom_script', 'shipper_source_s3_bucket') + "',", line)
    line = re.sub(r"^.*'--source_s3_path'.*$",
                  r"parser.add_argument('-sp', '--source_s3_path', default='" + \
                  config.get('custom_script', 'shipper_s3_bucket_directory') + "',", line)
    line = re.sub(r"^.*'--elk_pipeline_metric_namespace'.*$",
                  r"parser.add_argument('-en', '--elk_pipeline_metric_namespace', default='" + \
                  config.get('cloudwatch', 'elk_pipeline_metric_namespace') + "',", line)
    line = re.sub(r"^.*'--elk_pipeline_metric_name'.*$",
                  r"parser.add_argument('-em', '--elk_pipeline_metric_name', default='" + \
                  config.get('cloudwatch', 'elk_pipeline_metric_name') + "',", line)
    line = re.sub(r"^.*'--cooldown_period'.*$",
                  r"parser.add_argument('-cd', '--cooldown_period', default=" + \
                  config.get('custom_script', 'cooldown_period_minutes') + ",", line)              
    f2.write(line)
  f1.close()
  f2.close()

  # Connect AWS S3
  s3 = boto.s3.connect_to_region(region_name=config.get('general','aws_region'), 
                                 aws_access_key_id=config.get('general','aws_access_key_id'), 
                                 aws_secret_access_key=config.get('general','aws_secret_access_key')) 
  bucket = s3.get_bucket(config.get('custom_script', 's3_bucket'))
  k =  bucket.get_key(config.get('custom_script', 's3_bucket_directory') + filename)  
  if k is None :
    k = bucket.new_key(config.get('custom_script', 's3_bucket_directory') + filename)
  k.set_contents_from_filename('temp/' + filename)

  print 'Uploaded script ' + str(k)

#  custom script to 
def prepare_custom_scripts():
  print '------------------------------------'
  print 'Preparing ELK Custom Script'
  print '------------------------------------'

  from os import path
  for filename in os.listdir('custom_scripts') :
    upload_custom_script(filename)

  print 'Successfully prepared custom scripts'

# Prepares Pipeline Object Definition
def prepare_pipeline_object(definition) :
  new_definition = definition.replace('<pipeline_role>', 
                                      config.get('data_pipeline','pipeline_role'))
  new_definition = new_definition.replace('<pipeline_resource_role>', 
                                          config.get('data_pipeline','pipeline_resource_role'))
  new_definition = new_definition.replace('<aws_region>', 
                                          config.get('general','aws_region'))
  new_definition = new_definition.replace('<topic_arn>', 
                                          config.get('cloudwatch', 'topic_arn'))
  new_definition = new_definition.replace('<script_path>', 
                                          config.get('custom_script', 's3_bucket') + "/" + \
                                          config.get('custom_script', 's3_bucket_directory'))
  new_definition = new_definition.replace('<source_path>', 
                                          config.get('custom_script', 'shipper_source_s3_bucket') + "/" + \
                                          config.get('custom_script', 'shipper_s3_bucket_directory'))
  new_definition = new_definition.replace('<elk_pipeline_metric_name>',
                                          config.get('cloudwatch', 'elk_pipeline_metric_name'))
  new_definition = new_definition.replace('<elk_pipeline_metric_namespace>',
                                          config.get('cloudwatch', 'elk_pipeline_metric_namespace'))     
  return new_definition
  

# Builds the Vulnpryer Data Pipeline
def build_datapipeline() :
  print '------------------------------------'
  print 'Building ELK Orchestration Data Pipeline'
  print '------------------------------------'

  # Connect AWS Data Pipeline 
  dp = boto.datapipeline.connect_to_region(region_name=config.get('general','aws_region'), 
                                           aws_access_key_id=config.get('general','aws_access_key_id'), 
                                           aws_secret_access_key=config.get('general','aws_secret_access_key'))
  
  # Retrieve Data Pipeline ID by name
  search_marker=None
  while True:
    search_result =  dp.list_pipelines(marker=search_marker) 
    search_marker = search_result.get('marker')

    pipeline_ids = search_result.get('pipelineIdList')
    for i in range (0, len(pipeline_ids)):
      if pipeline_ids[i].get('name') == config.get('data_pipeline','pipeline_name'):
        print 'Pipeline with name ' +  config.get('data_pipeline','pipeline_name') + ' has been found. Dropping pipeline...'  
        dp.delete_pipeline( pipeline_ids[i].get('id'))
        break

    if not search_result.get('hasMoreResults') :
      break

  # Create new pipeline
  pipeline_id = dp.create_pipeline( config.get('data_pipeline','pipeline_name'),  
                                    config.get('data_pipeline','pipeline_name')).get('pipelineId')
  print 'Pipeline ' + config.get('data_pipeline','pipeline_name') + ' with ID ' + \
        pipeline_id + ' created on ' + config.get('general','aws_region') 

  # Prepare Pipeline Definition
  pipeline_objects = [config.get('data_pipeline','pipeline_schedule'), 
                      config.get('data_pipeline','pipeline_resource'), 
                      config.get('data_pipeline','pipeline_settings'), 
                      config.get('data_pipeline','pipeline_alarm_failure'),
                      config.get('data_pipeline','pipeline_alarm_success'), 
                      config.get('data_pipeline','pipeline_precondition_logstash_buffer_empty'), 
                      config.get('data_pipeline','pipeline_precondition_s3_empty'), 
                      config.get('data_pipeline','pipeline_precondition_has_keys'), 
                      config.get('data_pipeline','pipeline_precondition_s3_not_empty'), 
                      config.get('data_pipeline','pipeline_activity_scaleup_shipper_redis'),
                      config.get('data_pipeline','pipeline_activity_scaleup_indexer'),
                      config.get('data_pipeline','pipeline_activity_scaledown_shipper'), 
                      config.get('data_pipeline','pipeline_activity_scaledown_redis_indexer'),
                      config.get('data_pipeline','pipeline_activity_notification')]

  pipeline_definition = '' 
  for i in range (0,len(pipeline_objects)):
    pipeline_definition = pipeline_definition + prepare_pipeline_object(pipeline_objects[i])
    if i < len(pipeline_objects)-1 :
      pipeline_definition = pipeline_definition + ','

 
  dp.put_pipeline_definition( ast.literal_eval('[' + pipeline_definition  +  ']') , pipeline_id) 
 
  print 'Pipeline objects created'
  print 'Successfully built pipeline'    


# Create CloudWatch Alarm for the ELK Pipeline
def create_cloudwatch_alarm() :
  print '---------------------------------------------------------'
  print 'Create CloudWatch Alarm for ELK Pipeline'
  print '---------------------------------------------------------'

  cw = boto.ec2.cloudwatch.connect_to_region(region_name=config.get('general','aws_region'), 
                                             aws_access_key_id=config.get('general','aws_access_key_id'), 
                                             aws_secret_access_key=config.get('general','aws_secret_access_key'))

  # Intialize Custom Cloudwatch metric
  cw.put_metric_data(namespace=config.get('cloudwatch','elk_pipeline_metric_namespace'), 
                     name=config.get('cloudwatch','elk_pipeline_metric_name'), value=0) 
 
  # (Re)create alarm 
  cw.delete_alarms([config.get('cloudwatch','cw_alarm_elk_pipeline')])
  elk_pipeline_metric = cw.list_metrics(metric_name=config.get('cloudwatch','elk_pipeline_metric_name'),
                                        namespace=config.get('cloudwatch','elk_pipeline_metric_namespace'))
  elk_pipeline_metric[0].create_alarm(config.get('cloudwatch','cw_alarm_elk_pipeline'),
                                      comparison='>', threshold=0, period=60, statistic='Minimum',
                                      evaluation_periods=int(config.get('cloudwatch','overrunning_threshold_minutes')),
                                      alarm_actions=[config.get('cloudwatch','topic_arn')])
  print 'Created Cloudwatch alarm for ELK Pipeline'

#### MAIN ####
define_iam_roles()
prepare_custom_scripts()
build_datapipeline()
create_cloudwatch_alarm()
