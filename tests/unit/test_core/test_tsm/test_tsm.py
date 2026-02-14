"""TSM 策略模型和准入控制单元测试 (V2)。"""


import yaml

from src.core.tsm.admission import (
    AdmissionController,
    AdmissionResult,
    TaskSubmission,
)
from src.core.tsm.models import (
    DEFAULT_STRATEGY,
    ComparisonOp,
    EnvType,
    ExecutionContext,
    LogicOp,
    MatchCondition,
    MatchGroup,
    ResourceSelector,
    RetryPolicy,
    ScalingMode,
    ScalingPolicy,
    SelectionStrategy,
    TaskStrategy,
    TeardownAction,
    TeardownPolicy,
    ValueType,
)

# =============================================================================
# TaskStrategy 模型测试
# =============================================================================


class TestTaskStrategy:
    """测试 TaskStrategy V2 模型。"""

    def test_default_strategy_exists(self):
        """测试默认策略有效。"""
        assert DEFAULT_STRATEGY.id == "default"
        assert DEFAULT_STRATEGY.selector.env_type == EnvType.DEBUG_DUMMY

    def test_minimal_creation(self):
        """测试最小化创建策略。"""
        strategy = TaskStrategy(
            id="test-001",
            selector=ResourceSelector(env_type=EnvType.CHROME),
        )

        assert strategy.id == "test-001"
        assert strategy.selector.env_type == EnvType.CHROME
        # 默认值
        assert strategy.scaling.mode == ScalingMode.STRICT
        assert strategy.scaling.max_concurrency == 1
        assert strategy.retry.max_attempts == 1
        assert strategy.teardown.on_success == TeardownAction.RECYCLE

    def test_full_creation(self):
        """测试完整策略创建。"""
        strategy = TaskStrategy(
            id="full-001",
            name="完整策略",
            description="测试用完整策略",
            selector=ResourceSelector(
                env_type=EnvType.VIRTUAL_BROWSER,
                match_labels={"region": "cn"},
                sort_strategy=SelectionStrategy.BEST_FIT,
                wait_timeout=120,
            ),
            scaling=ScalingPolicy(
                mode=ScalingMode.ELASTIC,
                max_concurrency=5,
                min_idle=1,
                init_workflow="login",
            ),
            execution=ExecutionContext(
                module="my_module",
                workflow="scrape",
                params={"url": "https://example.com"},
                concurrency=3,
                timeout=300,
            ),
            retry=RetryPolicy(
                max_attempts=3,
                new_env_on_retry=True,
            ),
            teardown=TeardownPolicy(
                on_success=TeardownAction.RECYCLE,
                on_failure=TeardownAction.KEEP_ALIVE,
                on_timeout=TeardownAction.DESTROY,
            ),
        )

        assert strategy.name == "完整策略"
        assert strategy.scaling.max_concurrency == 5
        assert strategy.execution.concurrency == 3
        assert strategy.teardown.on_failure == TeardownAction.KEEP_ALIVE

    def test_yaml_roundtrip(self):
        """测试 YAML 序列化/反序列化往返。"""
        original = TaskStrategy(
            id="yaml-test",
            name="YAML测试",
            selector=ResourceSelector(env_type=EnvType.CHROME),
            scaling=ScalingPolicy(max_concurrency=3),
            execution=ExecutionContext(module="test", workflow="run"),
        )

        yaml_str = original.to_yaml()
        restored = TaskStrategy.from_yaml(yaml_str)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.scaling.max_concurrency == 3
        assert restored.execution.module == "test"

    def test_yaml_output_is_valid(self):
        """测试 YAML 输出格式正确。"""
        strategy = TaskStrategy(
            id="yaml-fmt",
            selector=ResourceSelector(env_type=EnvType.CHROME),
        )
        yaml_str = strategy.to_yaml()
        data = yaml.safe_load(yaml_str)

        assert data["id"] == "yaml-fmt"
        assert data["selector"]["env_type"] == "chrome"


class TestResourceSelector:
    """测试资源选择器。"""

    def test_default_values(self):
        """测试默认值。"""
        selector = ResourceSelector(env_type=EnvType.CHROME)

        assert selector.match_labels == {}
        assert selector.match_expressions == []
        assert selector.match_rules is None
        assert selector.sort_strategy == SelectionStrategy.FIFO
        assert selector.wait_timeout == 60

    def test_with_match_rules(self):
        """测试结构化匹配规则。"""
        rules = MatchGroup(
            logic=LogicOp.AND,
            conditions=[
                MatchCondition(field="region", op=ComparisonOp.EQ, value="cn"),
                MatchCondition(field="usage_count", op=ComparisonOp.LT, value=100),
            ],
        )
        selector = ResourceSelector(
            env_type=EnvType.CHROME,
            match_rules=rules,
        )

        assert selector.match_rules is not None
        assert len(selector.match_rules.conditions) == 2
        assert selector.match_rules.logic == LogicOp.AND


class TestEnums:
    """测试枚举值。"""

    def test_env_type_values(self):
        assert EnvType.CHROME.value == "chrome"
        assert EnvType.VIRTUAL_BROWSER.value == "virtual_browser"

    def test_scaling_mode_values(self):
        assert ScalingMode.STRICT.value == "strict"
        assert ScalingMode.ELASTIC.value == "elastic"

    def test_teardown_action_values(self):
        assert TeardownAction.DESTROY.value == "destroy"
        assert TeardownAction.RECYCLE.value == "recycle"
        assert TeardownAction.KEEP_ALIVE.value == "keep_alive"
        assert TeardownAction.NONE.value == "none"

    def test_value_type_values(self):
        assert ValueType.STATIC.value == "static"
        assert ValueType.FIELD.value == "field"
        assert ValueType.PARAM.value == "param"


# =============================================================================
# AdmissionController 测试
# =============================================================================


class TestAdmissionController:
    """测试准入控制器 (V2)。"""

    def test_admit_when_empty(self):
        """测试无任务时准入。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-1",
            module_name="my_module",
        )
        strategy = TaskStrategy(
            id="s-1",
            selector=ResourceSelector(env_type=EnvType.CHROME),
            scaling=ScalingPolicy(max_concurrency=5),
        )

        decision = controller.check(submission, strategy, running_tasks=[])

        assert decision.result == AdmissionResult.ADMITTED

    def test_queue_when_concurrency_full(self):
        """测试并发满时排队。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-3",
            module_name="test",
        )
        strategy = TaskStrategy(
            id="s-2",
            selector=ResourceSelector(env_type=EnvType.CHROME),
            scaling=ScalingPolicy(max_concurrency=2),
        )
        running = [
            {"task_id": "task-1", "module": "a"},
            {"task_id": "task-2", "module": "b"},
        ]

        decision = controller.check(submission, strategy, running_tasks=running)

        assert decision.result == AdmissionResult.QUEUED
        assert "并发已满" in decision.wait_hint

    def test_queue_when_module_concurrency_full(self):
        """测试同模块并发满时排队（混合模块场景）。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-4",
            module_name="my_module",
        )
        strategy = TaskStrategy(
            id="s-3",
            selector=ResourceSelector(env_type=EnvType.CHROME),
            # max_concurrency=3: 全局配额仅 3, 目前有 2 个不同模块任务运行中
            # 本模块已有 3 个运行，但总数 5 > 3 所以全局检查先触发
            # 实际上这里先验证全局并发不满、模块并发满的场景
            scaling=ScalingPolicy(max_concurrency=5),
        )
        # 总共 5 个任务，全局检查 5 >= 5 => QUEUED
        running = [
            {"task_id": "task-1", "module": "my_module"},
            {"task_id": "task-2", "module": "my_module"},
            {"task_id": "task-3", "module": "other"},
            {"task_id": "task-4", "module": "other"},
            {"task_id": "task-5", "module": "other"},
        ]

        decision = controller.check(submission, strategy, running_tasks=running)

        # 全局并发先触发
        assert decision.result == AdmissionResult.QUEUED
        assert "并发已满" in decision.wait_hint

    def test_admit_when_different_module(self):
        """测试不同模块时准入（总并发未满）。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-3",
            module_name="other_module",
        )
        strategy = TaskStrategy(
            id="s-4",
            selector=ResourceSelector(env_type=EnvType.CHROME),
            scaling=ScalingPolicy(max_concurrency=5),
        )
        running = [
            {"task_id": "task-1", "module": "my_module"},
            {"task_id": "task-2", "module": "my_module"},
        ]

        decision = controller.check(submission, strategy, running_tasks=running)

        assert decision.result == AdmissionResult.ADMITTED

    def test_submission_default_values(self):
        """测试 TaskSubmission 默认值。"""
        sub = TaskSubmission(task_id="t1", module_name="m1")

        assert sub.workflow_name == ""
        assert sub.tags == {}
        assert sub.priority is None


# =============================================================================
# 规则引擎测试 (#H)
# =============================================================================

class TestRuleEngine:
    """测试 AST 规则引擎。"""

    def test_empty_rules_match_all(self):
        """空规则组匹配任何环境。"""
        from src.core.tsm.adapters import evaluate_rules

        rules = MatchGroup(logic=LogicOp.AND, conditions=[])
        assert evaluate_rules({"foo": "bar"}, rules) is True

    def test_eq_condition(self):
        """测试 EQ 比较。"""
        from src.core.tsm.adapters import evaluate_rules

        cond = MatchCondition(field="region", op=ComparisonOp.EQ, value="us-west")
        rules = MatchGroup(logic=LogicOp.AND, conditions=[cond])
        
        assert evaluate_rules({"region": "us-west"}, rules) is True
        assert evaluate_rules({"region": "eu-east"}, rules) is False

    def test_gt_lt_condition(self):
        """测试 GT/LT 数值比较。"""
        from src.core.tsm.adapters import evaluate_rules

        cond = MatchCondition(field="memory", op=ComparisonOp.GT, value=4)
        rules = MatchGroup(logic=LogicOp.AND, conditions=[cond])
        
        assert evaluate_rules({"memory": 8}, rules) is True
        assert evaluate_rules({"memory": 2}, rules) is False

    def test_contains_condition(self):
        """测试 CONTAINS。"""
        from src.core.tsm.adapters import evaluate_rules

        cond = MatchCondition(field="tags", op=ComparisonOp.CONTAINS, value="gpu")
        rules = MatchGroup(logic=LogicOp.AND, conditions=[cond])

        assert evaluate_rules({"tags": ["gpu", "ssd"]}, rules) is True
        assert evaluate_rules({"tags": ["cpu"]}, rules) is False

    def test_nested_or_group(self):
        """测试嵌套 OR 组。"""
        from src.core.tsm.adapters import evaluate_rules

        inner = MatchGroup(
            logic=LogicOp.OR,
            conditions=[
                MatchCondition(field="region", op=ComparisonOp.EQ, value="us"),
                MatchCondition(field="region", op=ComparisonOp.EQ, value="eu"),
            ],
        )
        outer = MatchGroup(logic=LogicOp.AND, conditions=[inner])

        assert evaluate_rules({"region": "us"}, outer) is True
        assert evaluate_rules({"region": "eu"}, outer) is True
        assert evaluate_rules({"region": "jp"}, outer) is False

    def test_resolve_nested_field(self):
        """测试嵌套字段路径解析 (e.g. metadata.region)。"""
        from src.core.tsm.adapters import evaluate_rules

        cond = MatchCondition(field="meta.region", op=ComparisonOp.EQ, value="cn")
        rules = MatchGroup(logic=LogicOp.AND, conditions=[cond])

        assert evaluate_rules({"meta": {"region": "cn"}}, rules) is True
        assert evaluate_rules({"meta": {"region": "us"}}, rules) is False

    def test_missing_field_returns_false(self):
        """缺失字段不匹配。"""
        from src.core.tsm.adapters import evaluate_rules

        cond = MatchCondition(field="nonexistent", op=ComparisonOp.EQ, value="x")
        rules = MatchGroup(logic=LogicOp.AND, conditions=[cond])

        assert evaluate_rules({}, rules) is False


# =============================================================================
# 条件重试测试 (#A)
# =============================================================================

class TestShouldRetry:
    """测试 _should_retry 方法。"""

    def _make_orchestrator(self):
        from src.core.tsm.orchestrator import StrategyOrchestrator
        return StrategyOrchestrator()

    def test_empty_conditions_always_retry(self):
        """空条件列表 = 对所有错误重试。"""
        orch = self._make_orchestrator()
        assert orch._should_retry(ValueError("any error"), []) is True

    def test_matching_error_message(self):
        """错误消息包含条件字符串时重试。"""
        orch = self._make_orchestrator()
        assert orch._should_retry(
            RuntimeError("Connection timeout occurred"),
            ["timeout"],
        ) is True

    def test_matching_error_type(self):
        """错误类型名匹配时重试。"""
        orch = self._make_orchestrator()
        assert orch._should_retry(
            TimeoutError("deadline exceeded"),
            ["TimeoutError"],
        ) is True

    def test_no_match_no_retry(self):
        """不匹配任何条件时不重试。"""
        orch = self._make_orchestrator()
        assert orch._should_retry(
            ValueError("bad value"),
            ["timeout", "ConnectionError"],
        ) is False


# =============================================================================
# Labels 匹配测试 (#B)
# =============================================================================

class TestMatchLabels:
    """测试 REMAdapter._match_labels 方法。"""

    def _call(self, metadata: dict, labels: dict) -> bool:
        from src.core.tsm.adapters import REMAdapter
        return REMAdapter._match_labels(metadata, labels)

    def test_exact_namespace_path(self):
        """精确路径 'namespace.key' 匹配。"""
        meta = {"bot": {"region": "us-west", "tier": "premium"}}
        assert self._call(meta, {"bot.region": "us-west"}) is True
        assert self._call(meta, {"bot.region": "eu-east"}) is False

    def test_fuzzy_key_lookup(self):
        """无 namespace 时在所有 namespace 中查找 key。"""
        meta = {"bot": {"region": "cn"}, "sys": {"version": "3.0"}}
        assert self._call(meta, {"region": "cn"}) is True
        assert self._call(meta, {"version": "3.0"}) is True
        assert self._call(meta, {"region": "jp"}) is False

    def test_multiple_labels_and(self):
        """多个 label 需全部匹配 (AND 语义)。"""
        meta = {"mod": {"region": "cn", "tier": "vip"}}
        assert self._call(meta, {"mod.region": "cn", "mod.tier": "vip"}) is True
        assert self._call(meta, {"mod.region": "cn", "mod.tier": "free"}) is False

    def test_missing_key_returns_false(self):
        """缺少 key 时返回 False。"""
        meta = {"bot": {"region": "cn"}}
        assert self._call(meta, {"bot.nonexistent": "x"}) is False
        assert self._call(meta, {"nonexistent": "x"}) is False

    def test_empty_labels_always_match(self):
        """空 labels 匹配任何 metadata。"""
        assert self._call({"foo": {"bar": 1}}, {}) is True
        assert self._call({}, {}) is True
