"""
Reusable pipeline stack for deploying skills to ECS.

Creates a CodePipeline V2:
1. Source: GitHub with path-based filtering
2. Build: Docker build + ECR push (all target regions in one build)
3. [Optional] Manual Approval
4. Deploy stage(s): CDK deploy to ECS — one stage per region, sequential

Single-region (dev/qa/uat): one Deploy stage named "Deploy".
Multi-region (prod): Deploy-EUW1 then Deploy-USE1 sequentially in one pipeline.
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
from typing import List, Optional, Dict


class SkillPipelineStack(Stack):
    """
    Pipeline stack for a single skill in a single pipeline environment.

    Supports multi-region deployments via deploy_stages.
    Example (prod): deploy_stages=[
        {"environment": "prod-euw1", "region": "eu-west-1"},
        {"environment": "prod-use1", "region": "us-east-1"},
    ]
    The build stage pushes the Docker image to every region's ECR.
    Deploy stages run in order — euw1 fully completes before use1 starts.
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
        deploy_stages: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.skill_name = skill_name
        self.skill_path = skill_path
        self.deploy_env = environment

        # Resolve effective deploy stages.
        # Single-region (dev/qa/uat): not provided → defaults to pipeline's own region.
        # Multi-region (prod): caller provides ordered list, e.g. euw1 then use1.
        effective_deploy_stages: List[Dict[str, str]] = deploy_stages or [
            {"environment": environment, "region": self.region}
        ]

        # ── Artifact bucket ────────────────────────────────────────────────────
        artifact_bucket = s3.Bucket(
            self,
            "ArtifactBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
        )

        # ── Pipeline ───────────────────────────────────────────────────────────
        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=f"{skill_name}-{environment}",
            pipeline_type=codepipeline.PipelineType.V2,
            artifact_bucket=artifact_bucket,
            restart_execution_on_update=True,
        )

        # ── Source stage ───────────────────────────────────────────────────────
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
        pipeline.add_stage(stage_name="Source", actions=[source_action])

        # Path-based trigger filter (V2 feature) — only fire on changes to this skill
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
                                "Branches": {"Includes": [branch_name]},
                                "FilePaths": {"Includes": path_filters},
                            }
                        ],
                    },
                }
            ],
        )

        # ── Build stage ────────────────────────────────────────────────────────
        # Builds the Docker image once and pushes to all target regions' ECR repos.
        build_output = codepipeline.Artifact("BuildOutput")
        build_project = self._create_build_project(
            skill_path, environment, effective_deploy_stages
        )
        build_action = codepipeline_actions.CodeBuildAction(
            action_name="Docker_Build_Push",
            project=build_project,
            input=source_output,
            outputs=[build_output],
        )
        pipeline.add_stage(stage_name="Build", actions=[build_action])

        # ── Approval gate ──────────────────────────────────────────────────────
        # Sits between Build and the first Deploy. Covers all regions for prod.
        if require_approval:
            approval_action = codepipeline_actions.ManualApprovalAction(
                action_name="Manual_Approval",
                additional_information=f"Approve deployment of {skill_name} to {environment}",
            )
            pipeline.add_stage(stage_name="Approval", actions=[approval_action])

        # ── Deploy stages ──────────────────────────────────────────────────────
        # One stage per region, sequential. For single-region → "Deploy".
        # For multi-region → "Deploy-EUW1", "Deploy-USE1", etc.
        deploy_stage_names: List[str] = []
        for idx, stage_config in enumerate(effective_deploy_stages):
            deploy_env = stage_config["environment"]
            target_region = stage_config["region"]

            if len(effective_deploy_stages) == 1:
                stage_name = "Deploy"
            else:
                # "prod-euw1" → "Deploy-EUW1", "prod-use1" → "Deploy-USE1"
                suffix = deploy_env.split("-")[-1].upper()
                stage_name = f"Deploy-{suffix}"

            deploy_stage_names.append(stage_name)

            deploy_project = self._create_deploy_project(
                skill_path, deploy_env, target_region, idx
            )
            deploy_action = codepipeline_actions.CodeBuildAction(
                action_name="CDK_Deploy",
                project=deploy_project,
                input=source_output,
                extra_inputs=[build_output],
            )
            pipeline.add_stage(stage_name=stage_name, actions=[deploy_action])

        # ── Notifications ──────────────────────────────────────────────────────
        if notification_emails and len(notification_emails) > 0:
            self._create_notification_infrastructure(
                pipeline=pipeline,
                notification_emails=notification_emails,
                deploy_stage_names=deploy_stage_names,
            )

        # ── Outputs ────────────────────────────────────────────────────────────
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

    # ── Private helpers ────────────────────────────────────────────────────────

    def _create_build_project(
        self,
        skill_path: str,
        environment: str,
        deploy_stages: List[Dict[str, str]],
    ) -> codebuild.PipelineProject:
        """
        CodeBuild project: Docker build + ECR push to all target regions.

        For multi-region prod, the primary ENVIRONMENT drives the first ECR push.
        SECONDARY_DEPLOY_ENV / SECONDARY_DEPLOY_REGION drive the cross-region push
        inside build.yml (see cicd/buildspec/build.yml).
        """
        build_role = iam.Role(
            self,
            "BuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonEC2ContainerRegistryPowerUser"
                ),
            ],
        )

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

        # JFrog credentials live in the pipeline's own region (eu-west-1 for prod)
        build_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/a207920/leon-skills/jfrog/username",
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/a207920/leon-skills/jfrog/token",
                ],
            )
        )

        # ENVIRONMENT = primary deploy env (e.g. "prod-euw1") — drives ECR repo name and region.
        # ECR replication (configured at registry level) propagates the image to use1
        # automatically, so the build only needs to push once to the primary region.
        primary_env = deploy_stages[0]["environment"]

        env_vars = {
            "SKILL_PATH": codebuild.BuildEnvironmentVariable(value=skill_path),
            "ENVIRONMENT": codebuild.BuildEnvironmentVariable(value=primary_env),
            "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=self.account),
            # AWS_DEFAULT_REGION stays as the pipeline region for SSM JFrog creds lookup
            "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(value=self.region),
        }

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
            environment_variables=env_vars,
        )

    def _create_deploy_project(
        self,
        skill_path: str,
        deploy_env: str,
        target_region: str,
        idx: int,
    ) -> codebuild.PipelineProject:
        """
        CodeBuild project: CDK deploy for one specific region.

        deploy_env  — DEPLOYMENT_ENV value (e.g. "prod-euw1"), maps to region in config.py
        target_region — AWS region the skill deploys to (drives IAM policy ARNs)
        idx — 0-based index for unique CDK construct IDs in multi-stage pipelines
        """
        # Unique CDK construct ID suffix: idx=0 → "" (backward-compat), idx=1+ → "Use1", "Euw2", etc.
        id_suffix = "" if idx == 0 else deploy_env.split("-")[-1].capitalize()

        deploy_role = iam.Role(
            self,
            f"DeployRole{id_suffix}",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
        )

        # CloudFormation — scoped to target region
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudformation:*"],
                resources=[
                    f"arn:aws:cloudformation:{target_region}:{self.account}:stack/a207920-spx-*",
                ],
            )
        )

        # IAM — service roles only (NOT human-role/*)
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

        # ECS, EC2, ELB, Auto Scaling, CloudWatch Logs — these are scoped by the CDK deploy
        # context (region) so the broad resource ARNs are acceptable here
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecs:*"],
                resources=["*"],
            )
        )
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
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["elasticloadbalancing:*"],
                resources=["*"],
            )
        )
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

        # SSM — target region for skill config params; pipeline region for JFrog creds
        ssm_resources = [
            f"arn:aws:ssm:{target_region}:{self.account}:parameter/a207920/*",
        ]
        if target_region != self.region:
            ssm_resources.append(
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/a207920/*"
            )
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
                resources=ssm_resources,
            )
        )

        # S3 — CDK bootstrap assets bucket in target region (+ pipeline region if cross-region)
        s3_resources = [
            f"arn:aws:s3:::cdk-*-assets-{self.account}-{target_region}",
            f"arn:aws:s3:::cdk-*-assets-{self.account}-{target_region}/*",
            f"arn:aws:s3:::a207920-assets-{self.account}-{target_region}",
            f"arn:aws:s3:::a207920-assets-{self.account}-{target_region}/*",
        ]
        if target_region != self.region:
            s3_resources += [
                f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}",
                f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}/*",
                f"arn:aws:s3:::a207920-assets-{self.account}-{self.region}",
                f"arn:aws:s3:::a207920-assets-{self.account}-{self.region}/*",
            ]
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
                resources=s3_resources,
            )
        )

        # STS — TR CDK bootstrap roles in target region (+ pipeline region for cross-region)
        sts_resources = [
            f"arn:aws:iam::{self.account}:role/service-role/a207920-dr-{self.account}-{target_region}",
            f"arn:aws:iam::{self.account}:role/service-role/a207920-fpr-{self.account}-{target_region}",
            f"arn:aws:iam::{self.account}:role/service-role/a207920-ipr-{self.account}-{target_region}",
            f"arn:aws:iam::{self.account}:role/service-role/a207920-lr-{self.account}-{target_region}",
            f"arn:aws:iam::{self.account}:role/a207920-TrcdkToolkit-*",
            f"arn:aws:iam::{self.account}:role/a207920-CdkToolkit-*",
        ]
        if target_region != self.region:
            sts_resources += [
                f"arn:aws:iam::{self.account}:role/service-role/a207920-dr-{self.account}-{self.region}",
                f"arn:aws:iam::{self.account}:role/service-role/a207920-fpr-{self.account}-{self.region}",
                f"arn:aws:iam::{self.account}:role/service-role/a207920-ipr-{self.account}-{self.region}",
                f"arn:aws:iam::{self.account}:role/service-role/a207920-lr-{self.account}-{self.region}",
            ]
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRole"],
                resources=sts_resources,
            )
        )

        # PassRole — CloudFormation execution role in target region
        cfn_er_resources = [
            f"arn:aws:iam::{self.account}:role/service-role/a207920-cfn-er-{self.account}-{target_region}",
        ]
        if target_region != self.region:
            cfn_er_resources.append(
                f"arn:aws:iam::{self.account}:role/service-role/a207920-cfn-er-{self.account}-{self.region}"
            )
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=cfn_er_resources,
            )
        )

        return codebuild.PipelineProject(
            self,
            f"DeployProject{id_suffix}",
            project_name=f"{self.skill_name}-{deploy_env}-deploy",
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
                # ENVIRONMENT drives DEPLOYMENT_ENV in deploy.sh → config.py → correct region
                "ENVIRONMENT": codebuild.BuildEnvironmentVariable(value=deploy_env),
                # AWS_DEFAULT_REGION stays as pipeline region so JFrog SSM lookup works
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(value=self.region),
            },
        )

    def _create_notification_infrastructure(
        self,
        pipeline: codepipeline.Pipeline,
        notification_emails: List[str],
        deploy_stage_names: List[str],
    ) -> None:
        """
        Create notification infrastructure for deployment events.

        Creates:
        - SNS topic with email subscriptions
        - Lambda function to enrich notifications
        - EventBridge rules that watch all deploy stage names (for multi-region prod,
          both Deploy-EUW1 and Deploy-USE1 trigger notifications)
        """
        notification_topic = sns.Topic(
            self,
            "NotificationTopic",
            topic_name=f"{self.skill_name}-{self.deploy_env}-notifications",
            display_name=f"Deployment notifications for {self.skill_name} {self.deploy_env}",
        )

        for email in notification_emails:
            notification_topic.add_subscription(
                sns_subscriptions.EmailSubscription(email)
            )

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

        notification_topic.grant_publish(lambda_role)

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

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject", "s3:GetObjectVersion"],
                resources=[f"{pipeline.artifact_bucket.bucket_arn}/*"],
            )
        )

        # EventBridge rules match all deploy stage names.
        # For multi-region prod: ["Deploy-EUW1", "Deploy-USE1"] — each region completion
        # fires its own notification so you can track per-region success/failure.
        success_rule = events.Rule(
            self,
            "DeploymentSuccessRule",
            rule_name=f"{self.skill_name}-{self.deploy_env}-deploy-success",
            description=f"Notify on {self.skill_name} {self.deploy_env} deploy stage success",
            event_pattern=events.EventPattern(
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Stage Execution State Change"],
                detail={
                    "pipeline": [pipeline.pipeline_name],
                    "stage": deploy_stage_names,
                    "state": ["SUCCEEDED"],
                },
            ),
        )
        success_rule.add_target(events_targets.LambdaFunction(notification_lambda))

        failure_rule = events.Rule(
            self,
            "DeploymentFailureRule",
            rule_name=f"{self.skill_name}-{self.deploy_env}-deploy-failure",
            description=f"Notify on {self.skill_name} {self.deploy_env} deploy stage failure",
            event_pattern=events.EventPattern(
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Stage Execution State Change"],
                detail={
                    "pipeline": [pipeline.pipeline_name],
                    "stage": deploy_stage_names,
                    "state": ["FAILED"],
                },
            ),
        )
        failure_rule.add_target(events_targets.LambdaFunction(notification_lambda))

        cdk.CfnOutput(
            self,
            "NotificationTopicArn",
            value=notification_topic.topic_arn,
            description="SNS topic ARN for deployment notifications",
        )
