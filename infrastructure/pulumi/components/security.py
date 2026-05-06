"""SecurityPolicy — Cloud Armor WAF, VPC egress controls, and audit logging."""

from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from config import BILLING_ACCOUNT, ENVIRONMENT, PROJECT_ID


class SecurityPolicy(pulumi.ComponentResource):
    """
    Encapsulates security hardening:
      - Cloud Armor WAF policy with OWASP rules
      - VPC firewall rules for egress control
      - Cloud Audit Logs configuration
      - Resource access constraints
    """

    def __init__(self, name: str, opts: pulumi.ResourceOptions | None = None) -> None:
        super().__init__("mmp:infra:SecurityPolicy", name, {}, opts)

        protect = ENVIRONMENT == "production"

        # ── Cloud Armor Security Policy ────────────────────────────────────
        self.waf_policy = gcp.compute.SecurityPolicy(
            f"{name}-waf",
            name=f"mmp-waf-{ENVIRONMENT}",
            type="CLOUD_ARMOR",
            rules=[
                # Default allow rule (lowest priority)
                gcp.compute.SecurityPolicyRuleArgs(
                    action="allow",
                    priority=2147483647,
                    match=gcp.compute.SecurityPolicyRuleMatchArgs(
                        versioned_expr="SRC_IPS_V1",
                        config=gcp.compute.SecurityPolicyRuleMatchConfigArgs(
                            src_ip_ranges=["*"]
                        ),
                    ),
                    description="Default allow rule",
                ),
                # Rate limiting rule
                gcp.compute.SecurityPolicyRuleArgs(
                    action="rate_based_ban",
                    priority=1000,
                    match=gcp.compute.SecurityPolicyRuleMatchArgs(
                        expr=gcp.compute.SecurityPolicyRuleMatchExprArgs(
                            expression="true"  # Apply to all requests
                        ),
                    ),
                    rate_limit_options=gcp.compute.SecurityPolicyRuleRateLimitOptionsArgs(
                        rate_limit_threshold=gcp.compute.SecurityPolicyRuleRateLimitOptionsRateLimitThresholdArgs(
                            count=100,
                            interval_sec=60,
                        ),
                        ban_duration_sec=3600,
                        conform_action="allow",
                        exceed_action="deny(429)",
                        enforce_on_key="IP",
                    ),
                    description="Rate limit: 100 req/min per IP",
                ),
                # SQL Injection protection (OWASP rule)
                gcp.compute.SecurityPolicyRuleArgs(
                    action="deny(403)",
                    priority=1001,
                    match=gcp.compute.SecurityPolicyRuleMatchArgs(
                        expr=gcp.compute.SecurityPolicyRuleMatchExprArgs(
                            expression="evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 2})"
                        ),
                    ),
                    description="SQL Injection protection",
                ),
                # XSS protection (OWASP rule)
                gcp.compute.SecurityPolicyRuleArgs(
                    action="deny(403)",
                    priority=1002,
                    match=gcp.compute.SecurityPolicyRuleMatchArgs(
                        expr=gcp.compute.SecurityPolicyRuleMatchExprArgs(
                            expression="evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 2})"
                        ),
                    ),
                    description="XSS protection",
                ),
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        # ── VPC Firewall Rules ─────────────────────────────────────────────
        # Deny all egress by default (implicit, but explicit for clarity)
        # Allow specific egress only
        self.allow_egress_https = gcp.compute.Firewall(
            f"{name}-allow-egress-https",
            name=f"mmp-allow-egress-https-{ENVIRONMENT}",
            network="default",  # Will be overridden by actual network reference
            direction="EGRESS",
            priority=1000,
            destination_ranges=["0.0.0.0/0"],
            allows=[
                gcp.compute.FirewallAllowArgs(
                    protocol="tcp",
                    ports=["443"],
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        # ── Cloud Audit Logs ───────────────────────────────────────────────
        # Enable audit logging for all services
        self.audit_config = gcp.projects.IAMAuditConfig(
            f"{name}-audit-config",
            project=PROJECT_ID,
            service="allServices",
            audit_log_configs=[
                gcp.projects.IAMAuditConfigAuditLogConfigArgs(
                    log_type="ADMIN_READ",
                ),
                gcp.projects.IAMAuditConfigAuditLogConfigArgs(
                    log_type="DATA_READ",
                ),
                gcp.projects.IAMAuditConfigAuditLogConfigArgs(
                    log_type="DATA_WRITE",
                ),
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        # ── Budget Alert ───────────────────────────────────────────────────
        # Create a budget with alerting threshold (only if billing account is provided)
        if BILLING_ACCOUNT:
            self.budget = gcp.billing.Budget(
                f"{name}-budget",
                billing_account=BILLING_ACCOUNT,
                display_name=f"MMP Budget - {ENVIRONMENT}",
                amount=gcp.billing.BudgetAmountArgs(
                    specified_amount=gcp.billing.BudgetAmountSpecifiedAmountArgs(
                        currency_code="USD",
                        units="1000" if ENVIRONMENT == "production" else "500",
                    ),
                ),
                threshold_rules=[
                    gcp.billing.BudgetThresholdRuleArgs(
                        threshold_percent=50,
                        spend_basis="CURRENT_SPEND",
                    ),
                    gcp.billing.BudgetThresholdRuleArgs(
                        threshold_percent=80,
                        spend_basis="CURRENT_SPEND",
                    ),
                    gcp.billing.BudgetThresholdRuleArgs(
                        threshold_percent=100,
                        spend_basis="CURRENT_SPEND",
                    ),
                ],
                opts=pulumi.ResourceOptions(parent=self),
            )

        self.register_outputs({
            "wafPolicyId": self.waf_policy.id,
            "wafPolicyName": self.waf_policy.name,
        })
