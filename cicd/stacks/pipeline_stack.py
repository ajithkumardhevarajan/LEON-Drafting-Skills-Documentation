"""
Reusable pipeline stack for deploying skills to ECS.

Creates a 3-stage CodePipeline V2:
1. Source: GitHub with path-based filtering
2. Build: Docker build + ECR push
3. Deploy: CDK deploy to ECS

Each skill gets one stack per environment (e.g., urgent-drafting-dev, urgent-drafting-qa).
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as events_targets,
    RemovalPolicy,
    Duration,
)
from constructs import Construct
from typing import List, Optional


class SkillPipelineStack(Stack):
    """
    Pipeline stack for a single skill in a single environment.
    Uses CodePipeline V2 with path-based filtering.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        skill_name: str,
        skill_path: str,
        environment: str,
        branch_name: str,
        path_filters: List[str],
        codestar_connection_arn: str,
        github_owner: str,
        github_repo: str,
        require_approval: bool = False,
        notification_emails: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.skill_name = skill_name
        self.skill_path = skill_path
        self.deploy_env = environment

        # Create artifact bucket for pipeline
        artifact_bucket = s3.Bucket(
            self,
            "ArtifactBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
        )

        # Create the pipeline (V2)
        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=f"{skill_name}-{environment}",
            pipeline_type=codepipeline.PipelineType.V2,
            artifact_bucket=artifact_bucket,
            restart_execution_on_update=True,
        )

        # Source stage - GitHub with path filtering
        source_output = codepipeline.Artifact("SourceOutput")
        source_action = codepipeline_actions.CodeStarConnectionsSourceAction(
            action_name="GitHub_Source",
            owner=github_owner,
            repo=github_repo,
            branch=branch_name,
            output=source_output,
            connection_arn=codestar_connection_arn,
            trigger_on_push=True,
        )

        pipeline.add_stage(
            stage_name="Source",
            actions=[source_action],
        )

        # Add path-based trigger filter (V2 feature)
        # This ensures only changes to this skill's directory trigger the pipeline
        cfn_pipeline = pipeline.node.default_child
        cfn_pipeline.add_property_override(
            "Triggers",
            [
                {
                    "ProviderType": "CodeStarSourceConnection",
                    "GitConfiguration": {
                        "SourceActionName": "GitHub_Source",
                        "Push": [
                            {
                                "Branches": {
                                    "Includes": [branch_name],
                                },
                                "FilePaths": {
                                    "Includes": path_filters,
                                },
                            }
                        ],
                    },
                }
            ],
        )

        # Build stage - Docker build and push to ECR
        build_output = codepipeline.Artifact("BuildOutput")
        build_project = self._create_build_project(skill_path, environment)
        build_action = codepipeline_actions.CodeBuildAction(
            action_name="Docker_Build_Push",
            project=build_project,
            input=source_output,
            outputs=[build_output],
        )

        pipeline.add_stage(
            stage_name="Build",
            actions=[build_action],
        )

        # Optional manual approval
        if require_approval:
            approval_action = codepipeline_actions.ManualApprovalAction(
                action_name="Manual_Approval",
                additional_information=f"Approve deployment of {skill_name} to {environment}",
            )
            pipeline.add_stage(
                stage_name="Approval",
                actions=[approval_action],
            )

        # Deploy stage - CDK deploy
        deploy_project = self._create_deploy_project(skill_path, environment)
        deploy_action = codepipeline_actions.CodeBuildAction(
            action_name="CDK_Deploy",
            project=deploy_project,
            input=source_output,
            extra_inputs=[build_output],
        )

        pipeline.add_stage(
            stage_name="Deploy",
            actions=[deploy_action],
        )

        # Create notification infrastructure if emails are provided
        if notification_emails and len(notification_emails) > 0:
            self._create_notification_infrastructure(
                pipeline=pipeline,
                notification_emails=notification_emails,
            )

        # Outputs
        cdk.CfnOutput(
            self,
            "PipelineName",
            value=pipeline.pipeline_name,
            description=f"Pipeline name for {skill_name} {environment}",
        )

        cdk.CfnOutput(
            self,
            "PipelineConsoleUrl",
            value=f"https://{self.region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/{pipeline.pipeline_name}/view",
            description="Console URL for the pipeline",
        )

    def _create_build_project(self, skill_path: str, environment: str) -> codebuild.PipelineProject:
        """Create CodeBuild project for Docker build and ECR push."""

        # IAM role for build project
        build_role = iam.Role(
            self,
            "BuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser"),
            ],
        )

        # Add ECR permissions
        build_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:PutImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:CreateRepository",
                    "ecr:DescribeRepositories",
                ],
                resources=["*"],
            )
        )

        # Add SSM permissions for JFrog credentials
        build_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                ],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/a207920/leon-skills/jfrog/username",
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/a207920/leon-skills/jfrog/token",
                ],
            )
        )

        return codebuild.PipelineProject(
            self,
            "BuildProject",
            project_name=f"{self.skill_name}-{environment}-build",
            role=build_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
                compute_type=codebuild.ComputeType.SMALL,
                privileged=True,  # Required for Docker
            ),
            build_spec=codebuild.BuildSpec.from_source_filename(
                "cicd/buildspec/build.yml"
            ),
            environment_variables={
                "SKILL_PATH": codebuild.BuildEnvironmentVariable(value=skill_path),
                "ENVIRONMENT": codebuild.BuildEnvironmentVariable(value=environment),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=self.account),
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(value=self.region),
            },
        )

    def _create_deploy_project(self, skill_path: str, environment: str) -> codebuild.PipelineProject:
        """Create CodeBuild project for CDK deployment."""

        # IAM role for deploy project
        deploy_role = iam.Role(
            self,
            "DeployRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
        )

        # CloudFormation permissions for CDK deployment
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudformation:*"],
                resources=[
                    f"arn:aws:cloudformation:{self.region}:{self.account}:stack/a207920-spx-*",
                ],
            )
        )

        # IAM permissions for creating/managing service roles (NOT human-role/*)
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:PassRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:CreateServiceLinkedRole",
                ],
                resources=[
                    f"arn:aws:iam::{self.account}:role/a207920-spx-*",
                    f"arn:aws:iam::{self.account}:role/service-role/a207920-*",
                ],
            )
        )

        # ECS permissions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecs:*"],
                resources=["*"],
            )
        )

        # EC2 permissions for VPC resources
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeAvailabilityZones",
                    "ec2:CreateSecurityGroup",
                    "ec2:DeleteSecurityGroup",
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:AuthorizeSecurityGroupEgress",
                    "ec2:RevokeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupEgress",
                    "ec2:CreateTags",
                    "ec2:DeleteTags",
                ],
                resources=["*"],
            )
        )

        # Elastic Load Balancing permissions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["elasticloadbalancing:*"],
                resources=["*"],
            )
        )

        # SSM Parameter Store permissions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:PutParameter",
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:DeleteParameter",
                    "ssm:AddTagsToResource",
                    "ssm:RemoveTagsFromResource",
                ],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/a207920/*",
                ],
            )
        )

        # S3 permissions for CDK staging and artifacts
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:GetBucketPolicy",
                ],
                resources=[
                    f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}",
                    f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}/*",
                    f"arn:aws:s3:::a207920-assets-{self.account}-{self.region}",
                    f"arn:aws:s3:::a207920-assets-{self.account}-{self.region}/*",
                ],
            )
        )

        # ECR permissions (read images for deployment)
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:DescribeImages",
                    "ecr:DescribeRepositories",
                    "ecr:ListImages",
                ],
                resources=["*"],
            )
        )

        # Application Auto Scaling permissions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "application-autoscaling:RegisterScalableTarget",
                    "application-autoscaling:DeregisterScalableTarget",
                    "application-autoscaling:PutScalingPolicy",
                    "application-autoscaling:DeleteScalingPolicy",
                    "application-autoscaling:DescribeScalableTargets",
                    "application-autoscaling:DescribeScalingPolicies",
                ],
                resources=["*"],
            )
        )

        # CloudWatch Logs permissions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:PutRetentionPolicy",
                    "logs:DeleteLogGroup",
                    "logs:TagLogGroup",
                ],
                resources=["*"],
            )
        )

        # STS AssumeRole for TR CDK bootstrap roles (from a207920-CdkToolkit stack)
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRole"],
                resources=[
                    # TR CDK bootstrap roles
                    f"arn:aws:iam::{self.account}:role/service-role/a207920-dr-{self.account}-{self.region}",
                    f"arn:aws:iam::{self.account}:role/service-role/a207920-fpr-{self.account}-{self.region}",
                    f"arn:aws:iam::{self.account}:role/service-role/a207920-ipr-{self.account}-{self.region}",
                    f"arn:aws:iam::{self.account}:role/service-role/a207920-lr-{self.account}-{self.region}",
                    # Also support CDK toolkit roles
                    f"arn:aws:iam::{self.account}:role/a207920-TrcdkToolkit-*",
                    f"arn:aws:iam::{self.account}:role/a207920-CdkToolkit-*",
                ],
            )
        )

        # PassRole for CloudFormation execution role
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[
                    f"arn:aws:iam::{self.account}:role/service-role/a207920-cfn-er-{self.account}-{self.region}",
                ],
            )
        )

        return codebuild.PipelineProject(
            self,
            "DeployProject",
            project_name=f"{self.skill_name}-{environment}-deploy",
            role=deploy_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
                compute_type=codebuild.ComputeType.SMALL,
            ),
            build_spec=codebuild.BuildSpec.from_source_filename(
                "cicd/buildspec/deploy.yml"
            ),
            environment_variables={
                "SKILL_PATH": codebuild.BuildEnvironmentVariable(value=skill_path),
                "ENVIRONMENT": codebuild.BuildEnvironmentVariable(value=environment),
            },
        )

    def _create_notification_infrastructure(
        self,
        pipeline: codepipeline.Pipeline,
        notification_emails: List[str],
    ) -> None:
        """
        Create notification infrastructure for deployment events.

        Creates:
        - SNS topic with email subscriptions
        - Lambda function to enrich notifications
        - EventBridge rules to trigger on Deploy stage completion

        Args:
            pipeline: The CodePipeline to monitor
            notification_emails: List of email addresses to notify
        """
        # Create SNS topic
        notification_topic = sns.Topic(
            self,
            "NotificationTopic",
            topic_name=f"{self.skill_name}-{self.deploy_env}-notifications",
            display_name=f"Deployment notifications for {self.skill_name} {self.deploy_env}",
        )

        # Add email subscriptions
        for email in notification_emails:
            notification_topic.add_subscription(
                sns_subscriptions.EmailSubscription(email)
            )

        # Create IAM role for Lambda with explicit short name
        lambda_role = iam.Role(
            self,
            "NotificationLambdaRole",
            role_name=f"{self.skill_name}-{self.deploy_env}-notif-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # Create Lambda function for notification enrichment
        notification_lambda = lambda_.Function(
            self,
            "NotificationHandler",
            function_name=f"{self.skill_name}-{self.deploy_env}-notif-handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="notification_handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            environment={
                "SNS_TOPIC_ARN": notification_topic.topic_arn,
                "SKILL_NAME": self.skill_name,
                "ENVIRONMENT": self.deploy_env,
            },
        )

        # Grant Lambda permissions to publish to SNS
        notification_topic.grant_publish(lambda_role)

        # Allow Lambda to read pipeline execution details
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "codepipeline:GetPipelineExecution",
                    "codepipeline:GetPipelineState",
                    "codepipeline:ListPipelineExecutions",
                ],
                resources=[pipeline.pipeline_arn],
            )
        )

        # Allow Lambda to read artifacts from S3
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                ],
                resources=[
                    f"{pipeline.artifact_bucket.bucket_arn}/*",
                ],
            )
        )

        # EventBridge rule for Deploy stage SUCCESS
        success_rule = events.Rule(
            self,
            "DeploymentSuccessRule",
            rule_name=f"{self.skill_name}-{self.deploy_env}-deploy-success",
            description=f"Notify on {self.skill_name} {self.deploy_env} Deploy stage success",
            event_pattern=events.EventPattern(
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Stage Execution State Change"],
                detail={
                    "pipeline": [pipeline.pipeline_name],
                    "stage": ["Deploy"],
                    "state": ["SUCCEEDED"],
                },
            ),
        )

        # Add targets: Lambda for enrichment
        success_rule.add_target(events_targets.LambdaFunction(notification_lambda))

        # EventBridge rule for Deploy stage FAILURE
        failure_rule = events.Rule(
            self,
            "DeploymentFailureRule",
            rule_name=f"{self.skill_name}-{self.deploy_env}-deploy-failure",
            description=f"Notify on {self.skill_name} {self.deploy_env} Deploy stage failure",
            event_pattern=events.EventPattern(
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Stage Execution State Change"],
                detail={
                    "pipeline": [pipeline.pipeline_name],
                    "stage": ["Deploy"],
                    "state": ["FAILED"],
                },
            ),
        )

        # Add targets: Lambda for enrichment
        failure_rule.add_target(events_targets.LambdaFunction(notification_lambda))

        # Output
        cdk.CfnOutput(
            self,
            "NotificationTopicArn",
            value=notification_topic.topic_arn,
            description="SNS topic ARN for deployment notifications",
        )
