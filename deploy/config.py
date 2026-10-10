#!/usr/bin/env python3
"""Strict, non-secret deployment configuration and GitHub outputs."""
import json
import math
import os
import re
import sys
from pathlib import Path

FIELDS = {
    "project_id", "project_number", "region", "bucket_name", "bucket_prefix",
    "artifact_repository", "backend_service", "frontend_service",
    "backend_account", "frontend_account", "release_account", "provision_account",
    "github_repository", "github_branch", "wif_pool", "wif_provider",
    "billing_account", "budget_amount", "budget_currency", "notification_email",
    "frontend_requests_per_second", "errors_per_second",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path):
    config = json.loads(Path(path).read_text(), object_pairs_hook=unique_object,
                        parse_constant=lambda value: (_ for _ in ()).throw(
                            ValueError(f"Invalid JSON constant: {value}")))
    if not isinstance(config, dict) or set(config) != FIELDS:
        raise ValueError("Config must contain exactly the fields in config.example.json")
    for key, value in config.items():
        if key in {"budget_amount", "frontend_requests_per_second", "errors_per_second"}:
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be a finite positive number")
            if key == "budget_amount" and value > 1_000_000_000:
                raise ValueError("budget_amount must be at most 1 billion currency units")
        elif not isinstance(value, str) or not value or any(
            marker in value.upper() for marker in ("REPLACE", "CHANGEME", "TODO", "<", ">")
        ) or any(ord(char) < 32 for char in value):
            raise ValueError(f"{key} must be a non-placeholder, single-line string")
    patterns = {
        "project_id": r"[a-z][a-z0-9-]{4,28}[a-z0-9]",
        "project_number": r"[1-9][0-9]{5,20}",
        "region": r"[a-z]+-[a-z]+[0-9]",
        "bucket_name": r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]",
        "bucket_prefix": r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*",
        "github_repository": r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        "github_branch": r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*",
        "billing_account": r"[A-F0-9]{6}-[A-F0-9]{6}-[A-F0-9]{6}",
        "budget_currency": r"[A-Z]{3}",
        "notification_email": r"[^@\s,]+@[^@\s,]+\.[^@\s,]+",
    }
    for key in ("artifact_repository", "backend_service", "frontend_service",
                "wif_pool", "wif_provider"):
        patterns[key] = r"[a-z][a-z0-9-]{2,61}[a-z0-9]"
    for key in ("backend_account", "frontend_account", "release_account", "provision_account"):
        patterns[key] = r"[a-z][a-z0-9-]{4,28}[a-z0-9]"
    for key, pattern in patterns.items():
        if not re.fullmatch(pattern, config[key]):
            raise ValueError(f"Invalid {key}")
    accounts = [config[key] for key in (
        "backend_account", "frontend_account", "release_account", "provision_account")]
    if len(set(accounts)) != 4 or config["backend_service"] == config["frontend_service"]:
        raise ValueError("Runtime, release and provision identities/services must be distinct")
    return config


def outputs(config):
    project = config["project_id"]
    result = dict(config)
    result["workload_identity_provider"] = (
        f'projects/{config["project_number"]}/locations/global/'
        f'workloadIdentityPools/{config["wif_pool"]}/providers/{config["wif_provider"]}')
    for kind in ("release", "provision"):
        result[f"{kind}_service_account"] = f'{config[f"{kind}_account"]}@{project}.iam.gserviceaccount.com'
    return result


def check_github(configuration):
    if os.environ.get("GITHUB_REPOSITORY") != configuration["github_repository"]:
        raise ValueError("GitHub repository does not match configuration")
    if os.environ.get("GITHUB_REF") != f'refs/heads/{configuration["github_branch"]}':
        raise ValueError("GitHub branch does not match configuration")


if __name__ == "__main__":
    try:
        configuration = load(sys.argv[1])
        mode = sys.argv[2] if len(sys.argv) > 2 else "validate"
        if mode in ("shell", "outputs"):
            for key, value in outputs(configuration).items():
                print(f"{key.upper() if mode == 'shell' else key}={value}")
        elif mode != "validate":
            if mode != "check-github":
                raise ValueError("Mode must be validate, shell, outputs or check-github")
            check_github(configuration)
    except (ValueError, OSError, IndexError) as error:
        sys.exit(f"Configuration error: {error}")
