"""
Lambda function to enrich CodePipeline deployment notifications with image tag and commit info.

Triggered by EventBridge on Deploy stage completion (SUCCESS or FAILED).
Fetches IMAGE_TAG from build artifacts and commit info, then sends HTML email via SNS.
"""

import json
import os
import boto3
import zipfile
import io
from datetime import datetime
from typing import Dict, Any, Optional

# AWS clients
codepipeline = boto3.client("codepipeline")
s3 = boto3.client("s3")
sns = boto3.client("sns")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle CodePipeline state change events for Deploy stage.

    Args:
        event: EventBridge event with pipeline execution details
        context: Lambda context

    Returns:
        Response dict with status
    """
    try:
        print(f"Received event: {json.dumps(event)}")

        # Extract pipeline details from event
        detail = event.get("detail", {})
        pipeline_name = detail.get("pipeline")
        execution_id = detail.get("execution-id")
        state = detail.get("state")
        stage_name = detail.get("stage", "Deploy")

        if not all([pipeline_name, execution_id, state]):
            raise ValueError("Missing required fields in event")

        print(f"Processing {state} for {pipeline_name} execution {execution_id}")

        # Get pipeline execution details
        execution = codepipeline.get_pipeline_execution(
            pipelineName=pipeline_name,
            pipelineExecutionId=execution_id
        )

        # Extract skill info from pipeline name (format: skill-name-environment)
        parts = pipeline_name.rsplit("-", 1)
        skill_name = parts[0] if len(parts) > 1 else pipeline_name
        environment = parts[1] if len(parts) > 1 else "unknown"

        # Get image tag from build artifacts
        image_tag = get_image_tag_from_artifacts(pipeline_name, execution_id)

        # Get commit info
        commit_id, commit_message = get_commit_info(execution)

        # Get timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Format and send notification
        subject = format_email_subject(skill_name, environment, state, image_tag)
        body_text = format_email_body_text(
            skill_name=skill_name,
            environment=environment,
            state=state,
            image_tag=image_tag,
            commit_id=commit_id,
            commit_message=commit_message,
            execution_id=execution_id,
            timestamp=timestamp,
            pipeline_name=pipeline_name,
            stage_name=stage_name,
            region=os.environ.get("AWS_REGION", "eu-west-1"),
        )

        # Publish to SNS topic
        topic_arn = os.environ["SNS_TOPIC_ARN"]
        sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=body_text,
        )

        print(f"Notification sent successfully for {pipeline_name}")
        return {"statusCode": 200, "body": "Notification sent"}

    except Exception as e:
        print(f"Error processing notification: {str(e)}")
        raise


def get_image_tag_from_artifacts(pipeline_name: str, execution_id: str) -> Optional[str]:
    """
    Extract IMAGE_TAG from build artifacts in S3.

    Args:
        pipeline_name: Name of the pipeline
        execution_id: Pipeline execution ID

    Returns:
        Image tag or "unknown" if not found
    """
    try:
        # Get pipeline state to find artifact location
        response = codepipeline.get_pipeline_state(name=pipeline_name)

        # Find Build stage output artifact
        for stage in response.get("stageStates", []):
            if stage.get("stageName") == "Build":
                for action in stage.get("actionStates", []):
                    if action.get("actionName") == "Docker_Build_Push":
                        # Get artifact details
                        output_artifacts = action.get("outputArtifacts", [])
                        if output_artifacts:
                            artifact = output_artifacts[0]
                            s3_location = artifact.get("s3Location", {})
                            bucket = s3_location.get("bucket")
                            key = s3_location.get("key")

                            if bucket and key:
                                print(f"Downloading artifact from s3://{bucket}/{key}")

                                # Download the artifact ZIP file
                                obj = s3.get_object(Bucket=bucket, Key=key)
                                zip_content = obj["Body"].read()

                                # Extract and read imagetag.txt from the ZIP
                                with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                                    # Check if imagetag.txt exists in the ZIP
                                    if "imagetag.txt" in zip_file.namelist():
                                        with zip_file.open("imagetag.txt") as f:
                                            image_tag = f.read().decode("utf-8").strip()
                                            print(f"Found image tag: {image_tag}")
                                            return image_tag
                                    else:
                                        print("imagetag.txt not found in artifact")
                                        return "unknown"

        print("Build stage or artifact not found")
        return "unknown"
    except Exception as e:
        print(f"Error getting image tag: {str(e)}")
        import traceback
        traceback.print_exc()
        return "unknown"


def get_commit_info(execution: Dict[str, Any]) -> tuple[str, str]:
    """
    Extract commit ID and message from pipeline execution.

    Args:
        execution: Pipeline execution details

    Returns:
        Tuple of (commit_id, commit_message)
    """
    try:
        artifact_revisions = execution.get("pipelineExecution", {}).get("artifactRevisions", [])
        if artifact_revisions:
            revision = artifact_revisions[0]
            commit_id = revision.get("revisionId", "unknown")[:8]  # Short commit hash
            commit_message = revision.get("revisionSummary", "No commit message")
            return commit_id, commit_message
    except Exception as e:
        print(f"Error getting commit info: {str(e)}")

    return "unknown", "No commit information available"


def format_email_subject(skill_name: str, environment: str, state: str, image_tag: str) -> str:
    """Format email subject line."""
    env_upper = environment.upper()

    if state == "SUCCEEDED":
        return f"[{env_upper}] {skill_name} Deployed Successfully - {image_tag}"
    else:
        return f"[{env_upper}] {skill_name} Deployment FAILED"


def format_email_body_text(
    skill_name: str,
    environment: str,
    state: str,
    image_tag: str,
    commit_id: str,
    commit_message: str,
    execution_id: str,
    timestamp: str,
    pipeline_name: str,
    stage_name: str,
    region: str,
) -> str:
    """
    Format plain text email body.

    Args:
        skill_name: Name of the skill
        environment: Deployment environment (dev, qa, prod)
        state: Pipeline state (SUCCEEDED or FAILED)
        image_tag: Docker image tag
        commit_id: Short commit hash
        commit_message: Commit message
        execution_id: Pipeline execution ID
        timestamp: Timestamp of notification
        pipeline_name: Full pipeline name
        stage_name: Stage that triggered notification
        region: AWS region

    Returns:
        Plain text email body
    """
    # Status icon
    if state == "SUCCEEDED":
        status_icon = "✅"
        status_text = "Deployment Successful"
    else:
        status_icon = "❌"
        status_text = f"Deployment Failed at {stage_name} Stage"

    # Console URL
    console_url = f"https://{region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/{pipeline_name}/executions/{execution_id}/timeline"

    text = f"""{status_icon} {status_text}

Skill: {skill_name}
Environment: {environment.upper()}
Image Version: {image_tag}

Commit: {commit_id}
Message: {commit_message}

Execution ID: {execution_id}
Timestamp: {timestamp}

View Pipeline Execution:
{console_url}

---
AWS CodePipeline Deployment Notification
"""
    return text
