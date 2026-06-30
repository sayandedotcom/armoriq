import re
from typing import Any
from models import Rule, RuleType, ToolCall, PolicyResult, Decision
from store.models import RuleStore


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+above",
    r"disregard\s+your\s+instructions",
    r"new\s+instruction",
    r"override\s+your\s+programming",
    r"forget\s+everything",
    r"you\s+are\s+now\s+a\s+different",
    r"reveal\s+your\s+system\s+prompt",
    r"system\s+prompt\s+hacking",
]


def scan_for_injection(text: str) -> str | None:
    """Return the first injection pattern matched in `text`, or None."""
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            return pattern
    return None


class PolicyEngine:
    def __init__(self, rule_store: RuleStore):
        self.rule_store = rule_store

    def evaluate(self, tool_call: ToolCall, token_usage: int = 0) -> PolicyResult:
        rules = self.rule_store.get_enabled()
        rules.sort(key=lambda r: r.priority, reverse=True)

        decisions: list[PolicyResult] = []

        for rule in rules:
            result = self._check_rule(rule, tool_call, token_usage)
            if result.decision == Decision.DENY:
                return result
            if result.decision == Decision.REQUIRE_APPROVAL:
                decisions.append(result)

        if decisions:
            return decisions[0]

        return PolicyResult(decision=Decision.ALLOW, tool_call=tool_call)

    def _check_rule(self, rule: Rule, tool_call: ToolCall, token_usage: int) -> PolicyResult:
        if rule.rule_type == RuleType.BLOCK_TOOL:
            return self._check_block_tool(rule, tool_call)
        elif rule.rule_type == RuleType.REQUIRE_APPROVAL:
            return self._check_require_approval(rule, tool_call)
        elif rule.rule_type == RuleType.INPUT_VALIDATION:
            return self._check_input_validation(rule, tool_call)
        elif rule.rule_type == RuleType.TOKEN_BUDGET:
            return self._check_token_budget(rule, token_usage)
        elif rule.rule_type == RuleType.PROMPT_INJECTION_GUARD:
            return self._check_prompt_injection(rule, tool_call)

        return PolicyResult(decision=Decision.ALLOW, tool_call=tool_call)

    def _check_block_tool(self, rule: Rule, tool_call: ToolCall) -> PolicyResult:
        patterns = rule.config.get("patterns", [])
        tool_name = tool_call.name

        for pattern in patterns:
            if self._matches_pattern(tool_name, pattern):
                return PolicyResult(
                    decision=Decision.DENY,
                    reason=f"Tool '{tool_name}' is blocked by rule '{rule.name}'",
                    rule_id=rule.id,
                    tool_call=tool_call,
                )

        return PolicyResult(decision=Decision.ALLOW, tool_call=tool_call)

    def _check_require_approval(self, rule: Rule, tool_call: ToolCall) -> PolicyResult:
        patterns = rule.config.get("patterns", [])

        for pattern in patterns:
            if self._matches_pattern(tool_name := tool_call.name, pattern):
                return PolicyResult(
                    decision=Decision.REQUIRE_APPROVAL,
                    reason=f"Tool '{tool_name}' requires approval by rule '{rule.name}'",
                    rule_id=rule.id,
                    tool_call=tool_call,
                )

        return PolicyResult(decision=Decision.ALLOW, tool_call=tool_call)

    def _check_input_validation(self, rule: Rule, tool_call: ToolCall) -> PolicyResult:
        constraints = rule.config.get("constraints", {})

        for field_name, constraint in constraints.items():
            if field_name not in tool_call.arguments:
                continue

            value = tool_call.arguments[field_name]

            if "max_number" in constraint:
                max_val = constraint["max_number"]
                if isinstance(value, (int, float)) and value > max_val:
                    return PolicyResult(
                        decision=Decision.DENY,
                        reason=f"Field '{field_name}' value {value} exceeds maximum {max_val} by rule '{rule.name}'",
                        rule_id=rule.id,
                        tool_call=tool_call,
                    )

            if "min_number" in constraint:
                min_val = constraint["min_number"]
                if isinstance(value, (int, float)) and value < min_val:
                    return PolicyResult(
                        decision=Decision.DENY,
                        reason=f"Field '{field_name}' value {value} is below minimum {min_val} by rule '{rule.name}'",
                        rule_id=rule.id,
                        tool_call=tool_call,
                    )

            if "path_prefix" in constraint:
                prefix = constraint["path_prefix"]
                if isinstance(value, str) and not value.startswith(prefix):
                    return PolicyResult(
                        decision=Decision.DENY,
                        reason=f"Field '{field_name}' path '{value}' must start with '{prefix}' by rule '{rule.name}'",
                        rule_id=rule.id,
                        tool_call=tool_call,
                    )

            if "regex" in constraint:
                pattern = constraint["regex"]
                if isinstance(value, str) and not re.match(pattern, value):
                    return PolicyResult(
                        decision=Decision.DENY,
                        reason=f"Field '{field_name}' value '{value}' does not match pattern '{pattern}' by rule '{rule.name}'",
                        rule_id=rule.id,
                        tool_call=tool_call,
                    )

            if "allowed_values" in constraint:
                allowed = constraint["allowed_values"]
                if value not in allowed:
                    return PolicyResult(
                        decision=Decision.DENY,
                        reason=f"Field '{field_name}' value '{value}' not in allowed values {allowed} by rule '{rule.name}'",
                        rule_id=rule.id,
                        tool_call=tool_call,
                    )

        return PolicyResult(decision=Decision.ALLOW, tool_call=tool_call)

    def _check_token_budget(self, rule: Rule, token_usage: int) -> PolicyResult:
        max_tokens = rule.config.get("max_tokens", 0)
        if token_usage >= max_tokens:
            return PolicyResult(
                decision=Decision.DENY,
                reason=f"Token budget exceeded ({token_usage}/{max_tokens}) by rule '{rule.name}'",
                rule_id=rule.id,
            )
        return PolicyResult(decision=Decision.ALLOW)

    def _check_prompt_injection(self, rule: Rule, tool_call: ToolCall) -> PolicyResult:
        scan_inputs = rule.config.get("scan_inputs", True)

        if scan_inputs and scan_for_injection(str(tool_call.arguments)):
            return PolicyResult(
                decision=Decision.DENY,
                reason=f"Potential prompt injection detected in tool arguments by rule '{rule.name}'",
                rule_id=rule.id,
                tool_call=tool_call,
            )

        return PolicyResult(decision=Decision.ALLOW, tool_call=tool_call)

    def evaluate_result(self, tool_call: ToolCall, result_text: str) -> PolicyResult:
        """Scan a tool's *result* for injection (second-order / indirect attacks).

        Only PROMPT_INJECTION_GUARD rules with `scan_results` enabled apply here.
        Returns DENY if the returned content looks like it is trying to hijack
        the agent, so the poisoned output is never fed back to the model.
        """
        for rule in self.rule_store.get_enabled():
            if rule.rule_type != RuleType.PROMPT_INJECTION_GUARD:
                continue
            if not rule.config.get("scan_results", False):
                continue
            if scan_for_injection(result_text):
                return PolicyResult(
                    decision=Decision.DENY,
                    reason=f"Potential prompt injection detected in tool result by rule '{rule.name}'",
                    rule_id=rule.id,
                    tool_call=tool_call,
                )
        return PolicyResult(decision=Decision.ALLOW, tool_call=tool_call)

    def _matches_pattern(self, text: str, pattern: str) -> bool:
        bare_text = text.split("__")[-1] if "__" in text else text
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return bare_text.startswith(prefix) or text.startswith(prefix)
        elif "*" in pattern:
            regex_pattern = pattern.replace("*", ".*")
            return re.match(regex_pattern, bare_text) is not None or re.match(regex_pattern, text) is not None
        else:
            return bare_text == pattern or text == pattern
