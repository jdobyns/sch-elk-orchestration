sch-elk-orchestration
=====================

Prerequisites:

  - Parts of the ELK System already in place:
    - Opswork stack created, with shipper, redis and indexer layers
    - Logstash Buffer Custom CloudWatch Metric
    - S3 bucket/path of the logs to be processed by Shipper

  - Prepare the following:
    - SNS Topic ARN used for notification
    - S3 bucket/path created where custom scripts will be stored
    - S3 bucket/path created where DataPipeline will store logs


Instructions:

1. Python Boto at least v2.33.0 is needed to run. One can use the latest Amazon AMI Linux provided by AWS.

2. Download the code

         https://github.com/cascadeo/sch-elk-orchestration.git

3. Create an IAM user for ELK. The Data Pipeline objects will be owned by this user. Pipelines aren't visible to other IAM users in the account so a generic IAM user should be used for management.

         https://forums.aws.amazon.com/thread.jspa?threadID=138201

4. Configure IAM User.
         - Generate access keys
         - Set its permission policy to iam_policies/iam_user_policy

5. Populate configuration cfg file with desired values. Descriptions are placed above the parameters as comments.

6. Run the script

         python deploy_elk_orchestration.py

  
     High level description of what the script does:
       - Prepares the IAM roles. Sets their permission and trust policies which are defined under iam_policies folder
       - Prepares the custom monitoring scripts and uploads them to S3
       - Drops and rebuilds the Data Pipeline
       - Creates Cloudwatch alarm for each opsworks layer - shipper, redis and indexer

7. Log on as your IAM User to the AWS Data Pipeline console on the specified region.

8. Make sure all instances in the Opswork stack are stopped. Activate to run the Pipeline.

