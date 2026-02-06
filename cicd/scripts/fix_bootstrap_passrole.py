#!/usr/bin/env python3
"""
Fix CDK Bootstrap PassRole Policy for TR Permission Boundary

This script automates fixing the PassRole policy in the CDK bootstrap stack
to work with TR's permission boundary by changing the role path from
human-role/* to service-role/*.

Usage:
    # Export and review the fix (does not apply)
    python fix_bootstrap_passrole.py --account 060725138335 --region eu-west-1

    # Apply the fix
    python fix_bootstrap_passrole.py --account 060725138335 --region eu-west-1 --apply

    # Use specific AWS profile
    python fix_bootstrap_passrole.py --account 060725138335 --region eu-west-1 --profile tr-central-preprod --apply
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Tuple
import subprocess


def run_aws_command(cmd: list[str], capture_output: bool = True) -> Tuple[int, str, str]:
    """Run AWS CLI command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def get_bootstrap_template(stack_name: str, profile: str = None, region: str = "eu-west-1") -> Dict[str, Any]:
    """
    Fetch the current bootstrap template from CloudFormation.

    Args:
        stack_name: Name of the bootstrap stack
        profile: AWS profile to use (optional)
        region: AWS region

    Returns:
        Template as a dictionary

    Raises:
        RuntimeError: If template cannot be fetched
    """
    cmd = ["aws", "cloudformation", "get-template", "--stack-name", stack_name, "--region", region]
    if profile:
        cmd.extend(["--profile", profile])

    returncode, stdout, stderr = run_aws_command(cmd)

    if returncode != 0:
        raise RuntimeError(f"Failed to fetch bootstrap template: {stderr}")

    try:
        template_response = json.loads(stdout)
        template_body = template_response.get("TemplateBody")

        if isinstance(template_body, str):
            return json.loads(template_body)
        return template_body
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse template JSON: {e}")


def fix_passrole_policy(template: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Fix the PassRole policy in the bootstrap template.

    Changes the PassRole resource from:
        arn:aws:iam::*:role/human-role/*
    to:
        arn:aws:iam::*:role/service-role/*

    Args:
        template: CloudFormation template dictionary

    Returns:
        Tuple of (fixed_template, was_modified)
    """
    modified = False
    resources = template.get("Resources", {})

    # Find the CloudFormation execution role
    for resource_name, resource in resources.items():
        if resource.get("Type") == "AWS::IAM::Role":
            policies = resource.get("Properties", {}).get("Policies", [])

            for policy in policies:
                if policy.get("PolicyName") == "CDKAssumeRolePolicy":
                    statements = policy.get("PolicyDocument", {}).get("Statement", [])

                    for statement in statements:
                        if statement.get("Action") == "iam:PassRole":
                            resource_arn = statement.get("Resource", "")

                            # Check if it's using human-role path
                            if "human-role" in resource_arn:
                                # Fix the path
                                statement["Resource"] = resource_arn.replace(
                                    "human-role", "service-role"
                                )
                                modified = True
                                print(f"✓ Fixed PassRole policy in resource: {resource_name}")
                                print(f"  Old: {resource_arn}")
                                print(f"  New: {statement['Resource']}")

    return template, modified


def update_bootstrap_stack(
    stack_name: str,
    template: Dict[str, Any],
    profile: str = None,
    region: str = "eu-west-1",
    dry_run: bool = False
) -> bool:
    """
    Update the bootstrap stack with the fixed template.

    Args:
        stack_name: Name of the bootstrap stack
        template: Fixed template dictionary
        profile: AWS profile to use (optional)
        region: AWS region
        dry_run: If True, only show what would be done

    Returns:
        True if update succeeded or dry_run, False otherwise
    """
    # Save template to temporary file
    template_file = Path("bootstrap-template-fixed.json")
    with open(template_file, "w") as f:
        json.dump(template, f, indent=2)

    print(f"\n✓ Saved fixed template to: {template_file}")

    if dry_run:
        print("\n⚠️  DRY RUN: Template saved but stack not updated")
        print(f"   To apply the fix, run:")
        print(f"   aws cloudformation update-stack \\")
        print(f"     --stack-name {stack_name} \\")
        print(f"     --template-body file://{template_file} \\")
        print(f"     --capabilities CAPABILITY_NAMED_IAM \\")
        if profile:
            print(f"     --profile {profile} \\")
        print(f"     --region {region}")
        return True

    print("\n⚠️  Updating bootstrap stack...")
    cmd = [
        "aws", "cloudformation", "update-stack",
        "--stack-name", stack_name,
        "--template-body", f"file://{template_file}",
        "--capabilities", "CAPABILITY_NAMED_IAM",
        "--region", region
    ]
    if profile:
        cmd.extend(["--profile", profile])

    returncode, stdout, stderr = run_aws_command(cmd)

    if returncode != 0:
        if "No updates are to be performed" in stderr:
            print("✓ Stack is already up to date (no changes needed)")
            return True
        else:
            print(f"✗ Failed to update stack: {stderr}")
            return False

    print("✓ Stack update initiated")
    print(f"   Stack update ID: {json.loads(stdout).get('StackId', 'unknown')}")
    print("\n   Waiting for stack update to complete...")
    print("   You can monitor progress in the AWS Console or run:")
    print(f"   aws cloudformation wait stack-update-complete --stack-name {stack_name}", end="")
    if profile:
        print(f" --profile {profile}", end="")
    print(f" --region {region}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Fix CDK Bootstrap PassRole policy for TR permission boundary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export and review (does not apply changes)
  python fix_bootstrap_passrole.py --account 060725138335 --region eu-west-1

  # Apply the fix
  python fix_bootstrap_passrole.py --account 060725138335 --region eu-west-1 --apply

  # Use specific AWS profile
  python fix_bootstrap_passrole.py --account 060725138335 --region eu-west-1 --profile tr-central-preprod --apply
        """
    )

    parser.add_argument(
        "--account",
        required=True,
        help="AWS account ID (e.g., 060725138335)"
    )
    parser.add_argument(
        "--region",
        default="eu-west-1",
        help="AWS region (default: eu-west-1)"
    )
    parser.add_argument(
        "--profile",
        help="AWS profile to use (optional, uses default if not specified)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the fix (default: export only)"
    )
    parser.add_argument(
        "--stack-name",
        default="a207920-spx-CDKToolkit",
        help="Bootstrap stack name (default: a207920-spx-CDKToolkit)"
    )

    args = parser.parse_args()

    print(f"CDK Bootstrap PassRole Fix")
    print(f"=" * 50)
    print(f"Account: {args.account}")
    print(f"Region:  {args.region}")
    print(f"Profile: {args.profile or '(default)'}")
    print(f"Stack:   {args.stack_name}")
    print(f"Mode:    {'APPLY CHANGES' if args.apply else 'EXPORT ONLY'}")
    print(f"=" * 50)
    print()

    try:
        # Step 1: Fetch current template
        print("1. Fetching current bootstrap template...")
        template = get_bootstrap_template(args.stack_name, args.profile, args.region)
        print("✓ Template fetched successfully")

        # Step 2: Fix the PassRole policy
        print("\n2. Analyzing and fixing PassRole policy...")
        fixed_template, modified = fix_passrole_policy(template)

        if not modified:
            print("✓ No changes needed - PassRole policy already uses service-role path")
            return 0

        # Step 3: Update the stack or export
        print("\n3. Updating bootstrap stack...")
        success = update_bootstrap_stack(
            args.stack_name,
            fixed_template,
            args.profile,
            args.region,
            dry_run=not args.apply
        )

        if success:
            print("\n" + "=" * 50)
            print("✓ Bootstrap fix completed successfully")
            print("=" * 50)
            return 0
        else:
            print("\n" + "=" * 50)
            print("✗ Bootstrap fix failed")
            print("=" * 50)
            return 1

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
