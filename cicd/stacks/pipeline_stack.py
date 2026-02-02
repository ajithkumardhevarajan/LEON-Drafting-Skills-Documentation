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
    RemovalPolicy,
)
from constructs import Construct
from typing import List


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

        # Add CDK deployment permissions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudformation:*",
                    "ecs:*",
                    "ec2:*",
                    "elasticloadbalancing:*",
                    "iam:*",
                    "logs:*",
                    "ecr:*",
                    "ssm:*",
                    "s3:*",
                    "kms:*",
                ],
                resources=["*"],
            )
        )

        # Add permissions to assume CDK execution roles
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRole"],
                resources=[
                    f"arn:aws:iam::{self.account}:role/cdk-*",
                    f"arn:aws:iam::{self.account}:role/a207920-TrcdkToolkit-*",
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
