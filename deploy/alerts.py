#!/usr/bin/env python3
"""Reconcile dedicated Monitoring resources and a whole-project monthly budget."""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

from config import load


class API:
    def __init__(self):
        self.token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"], text=True).strip()

    def request(self, method, url, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{method} {url}: HTTP {error.code}: "
                               f"{error.read().decode()}") from error

    def list(self, url, field):
        items = []
        page = ""
        while True:
            result = self.request("GET", url + (
                "?pageToken=" + urllib.parse.quote(page, safe="") if page else ""))
            items.extend(result.get(field, []))
            page = result.get("nextPageToken", "")
            if not page:
                return items

    def upsert(self, url, field, payload, mask):
        matches = [item for item in self.list(url, field)
                   if item.get("displayName") == payload["displayName"]]
        if len(matches) > 1:
            raise ValueError(f"Duplicate managed displayName: {payload['displayName']}")
        if matches:
            name = matches[0]["name"]
            base = url.split("/projects/")[0] if "/projects/" in url else url.split("/billingAccounts/")[0]
            return self.request("PATCH", f"{base}/{name}?updateMask={mask}", {
                **payload, "name": name})
        return self.request("POST", url, payload)


def channel_payload(config):
    return {
        "type": "email", "displayName": f'{config["project_id"]} deployment email',
        "labels": {"email_address": config["notification_email"]},
        "enabled": True,
    }


def policy_payload(config, service, kind, channel):
    error = kind == "errors"
    metric_filter = (
        'resource.type = "cloud_run_revision" AND '
        'metric.type = "run.googleapis.com/request_count" AND '
        f'resource.labels.project_id = "{config["project_id"]}" AND '
        f'resource.labels.location = "{config["region"]}" AND '
        f'resource.labels.service_name = "{service}"'
    )
    if error:
        metric_filter += ' AND metric.labels.response_code_class = "5xx"'
    return {
        "displayName": f'{config["project_id"]} {service} {kind}',
        "combiner": "OR", "enabled": True, "notificationChannels": [channel],
        "conditions": [{
            "displayName": f"Aggregate {kind} rate over all revisions and instances",
            "conditionThreshold": {
                "filter": metric_filter, "comparison": "COMPARISON_GT",
                "thresholdValue": config["errors_per_second" if error else "frontend_requests_per_second"],
                "duration": "300s",
                "aggregations": [{
                    "alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM", "groupByFields": [],
                }],
                "trigger": {"count": 1},
                "evaluationMissingData": "EVALUATION_MISSING_DATA_INACTIVE",
            },
        }],
        "alertStrategy": {"autoClose": "1800s"},
    }


def budget_payload(config, channel):
    amount = Decimal(str(config["budget_amount"]))
    if amount != amount.quantize(Decimal("0.000000001")):
        raise ValueError("Budget amount cannot have more than 9 fractional digits")
    return {
        "displayName": f'{config["project_id"]} monthly project budget',
        "budgetFilter": {
            "projects": [f'projects/{config["project_number"]}'],
            "calendarPeriod": "MONTH", "creditTypesTreatment": "INCLUDE_ALL_CREDITS",
        },
        "amount": {"specifiedAmount": {
            "currencyCode": config["budget_currency"], "units": str(int(amount)),
            "nanos": int((amount - int(amount)) * 1_000_000_000),
        }},
        "thresholdRules": [
            {"thresholdPercent": percent, "spendBasis": "CURRENT_SPEND"}
            for percent in (0.5, 0.8, 1.0)
        ] + [{"thresholdPercent": 1.0, "spendBasis": "FORECASTED_SPEND"}],
        "allUpdatesRule": {
            "monitoringNotificationChannels": [channel],
            "disableDefaultIamRecipients": True,
        },
    }


def main(config):
    api = API()
    billing = api.request(
        "GET", f'https://cloudbilling.googleapis.com/v1/projects/{config["project_id"]}/billingInfo')
    if not billing.get("billingEnabled") or billing.get("billingAccountName") != (
        f'billingAccounts/{config["billing_account"]}'
    ):
        raise ValueError("Project must be billing-enabled on the configured billing account")
    monitoring = f'https://monitoring.googleapis.com/v3/projects/{config["project_id"]}'
    channel = api.upsert(
        f"{monitoring}/notificationChannels", "notificationChannels", channel_payload(config),
        "displayName,labels,enabled")["name"]
    for service, kind in (
        (config["frontend_service"], "traffic"), (config["frontend_service"], "errors"),
        (config["backend_service"], "errors"),
    ):
        api.upsert(f"{monitoring}/alertPolicies", "alertPolicies",
                   policy_payload(config, service, kind, channel),
                   "displayName,combiner,enabled,notificationChannels,conditions,alertStrategy")
    api.upsert(
        f'https://billingbudgets.googleapis.com/v1/billingAccounts/{config["billing_account"]}/budgets',
        "budgets", budget_payload(config, channel),
        "displayName,budgetFilter,amount,thresholdRules,allUpdatesRule")
    print("Email channel, three aggregate rate alerts and monthly budget reconciled.")


if __name__ == "__main__":
    try:
        main(load(sys.argv[1]))
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(f"Alert provisioning error: {error}")
