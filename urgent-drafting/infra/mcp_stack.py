"""
CDK stack for deploying urgent-drafting MCP server to ECS behind ALB.
Based on the story-search-mcp infrastructure pattern.
"""

from typing import Optional

from aws_cdk import (
    Stack,
    Duration,
    DefaultStackSynthesizer,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ssm as ssm,
    aws_logs as logs,
    RemovalPolicy
)
from constructs import Construct
from tr_cdk_lib import StackContextAccessor

from config import MCPConfig


class MCPStack(Stack):
    """
    CDK Stack for deploying urgent-drafting MCP server to ECS with ALB.

    This stack creates:
    - ECS Cluster
    - Fargate Task Definition with IAM roles
    - Application Load Balancer (ALB)
    - ECS Service with auto-scaling
    - CloudWatch Log Groups
    - SSM Parameters for configuration
    """

    def __init__(self, scope: Construct, construct_id: str, config: MCPConfig,
                 image_tag: Optional[str] = None, **kwargs) -> None:

        # Configure to use the service role for CloudFormation execution
        # This fixes the PassRole error by using a role in service-role/ path
        # instead of human-role/ path (which is blocked by tr-permission-boundary)
        if 'synthesizer' not in kwargs:
            cfn_exec_role = f"arn:aws:iam::{config.aws_account}:role/service-role/a207920-cfn-er-{config.aws_account}-{config.aws_region}"
            kwargs['synthesizer'] = DefaultStackSynthesizer(
                cloud_formation_execution_role=cfn_exec_role
            )

        super().__init__(scope, construct_id, **kwargs)

        self.config = config
        self.image_tag = image_tag or config.default_image_tag

        # Create ECS cluster
        self.cluster = self._create_cluster()

        # Create IAM roles
        self.task_role, self.execution_role = self._create_iam_roles()

        # Create task definition and container
        self.task_definition = self._create_task_definition()

        # Create load balancer explicitly for readable naming
        self.load_balancer = self._create_load_balancer()

        # Create load-balanced Fargate service
        self.fargate_service = self._create_load_balanced_service()

        # Setup auto-scaling
        self._setup_auto_scaling()

        # Create SSM parameters
        self._create_ssm_parameters()

    def _create_cluster(self) -> ecs.Cluster:
        """Create ECS cluster"""
        return ecs.Cluster(
            self,
            "Cluster",
            cluster_name=self.config.get_resource_name("cluster"),
            vpc=StackContextAccessor.tr_context(self).vpc,
            container_insights=True,
        )

    def _create_iam_roles(self):
        """Create IAM roles for ECS tasks"""
        # Task execution role (for pulling images and writing logs)
        # Note: Not specifying role_name - let TR CDK auto-generate to avoid 64-char limit
        execution_role = iam.Role(
            self,
            "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # Task role (for application permissions)
        # Note: Not specifying role_name - let TR CDK auto-generate to avoid 64-char limit
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Grant SSM parameter access to task role
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{self.config.aws_region}:{self.config.aws_account}:parameter{self.config.ssm_parameter_prefix}/*"
                ],
            )
        )

        return task_role, execution_role

    def _create_task_definition(self) -> ecs.FargateTaskDefinition:
        """Create Fargate task definition with container"""
        task_def = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=self.config.get_resource_name("task"),
            cpu=self.config.cpu,
            memory_limit_mib=self.config.memory_mib,
            execution_role=self.execution_role,
            task_role=self.task_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )

        # Get environment variables from config
        env_vars = self.config.get_environment_variables()

        # Create CloudWatch log group
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/aws/ecs/{self.config.get_resource_name('service')}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create container image reference using repository name
        image = ecs.ContainerImage.from_ecr_repository(
            ecr.Repository.from_repository_name(
                self, "ECRRepo", self.config.ecr_repository_name
            ),
            tag=self.image_tag,
        )

        # Add container
        container = task_def.add_container(
            "Container",
            container_name=f"{self.config.service_name}-container",
            image=image,
            logging=ecs.LogDriver.aws_logs(
                stream_prefix=self.config.service_name,
                log_group=log_group,
            ),
            environment=env_vars,
        )

        container.add_port_mappings(
            ecs.PortMapping(
                container_port=self.config.container_port,
                protocol=ecs.Protocol.TCP
            )
        )

        return task_def

    def _create_load_balancer(self) -> elbv2.ApplicationLoadBalancer:
        """Create application load balancer with readable name"""
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "LoadBalancer",
            load_balancer_name=self.config.get_resource_name("alb"),
            vpc=StackContextAccessor.tr_context(self).vpc,
            internet_facing=self.config.public_load_balancer,
        )
        return alb

    def _create_load_balanced_service(self) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        """Create application load-balanced Fargate service"""
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            service_name=self.config.get_resource_name("service"),
            cluster=self.cluster,
            memory_limit_mib=self.config.memory_mib,
            desired_count=self.config.desired_count,
            cpu=self.config.cpu,
            min_healthy_percent=100,
            task_definition=self.task_definition,
            load_balancer=self.load_balancer,  # Use explicit ALB with readable name
            public_load_balancer=self.config.public_load_balancer,
            health_check_grace_period=Duration.seconds(120),  # Give container time to start
        )

        # Configure health check on target group
        fargate_service.target_group.configure_health_check(
            path="/health",
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,  # Increase tolerance for startup
            timeout=Duration.seconds(30),
            interval=Duration.seconds(60),
            healthy_http_codes="200",
        )

        return fargate_service

    def _setup_auto_scaling(self):
        """Configure auto-scaling for the ECS service"""
        scalable_target = self.fargate_service.service.auto_scale_task_count(
            min_capacity=self.config.min_capacity,
            max_capacity=self.config.max_capacity
        )

        # CPU-based scaling
        scalable_target.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=self.config.cpu_target_utilization,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        # Memory-based scaling
        scalable_target.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=self.config.memory_target_utilization,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

    def _create_ssm_parameters(self):
        """Create SSM parameters for service discovery"""
        ssm.StringParameter(
            self,
            "AlbDnsParameter",
            parameter_name=self.config.get_ssm_parameter_name("alb-dns"),
            string_value=self.fargate_service.load_balancer.load_balancer_dns_name,
            description=f"ALB DNS name for {self.config.service_name}",
        )

        ssm.StringParameter(
            self,
            "ServiceUrlParameter",
            parameter_name=self.config.get_ssm_parameter_name("service-url"),
            string_value=f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}",
            description=f"Service URL for {self.config.service_name}",
        )

        ssm.StringParameter(
            self,
            "ServiceArnParameter",
            parameter_name=self.config.get_ssm_parameter_name("service-arn"),
            string_value=self.fargate_service.service.service_arn,
            description=f"ECS Service ARN for {self.config.service_name}",
        )
