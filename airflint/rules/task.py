import ast
from copy import deepcopy

from refactor import ReplacementAction, Rule
from refactor.context import Scope

from airflint.actions import AddNewImport
from airflint.representatives import ImportFinder, PythonCallableFinder


class _AddTaskDecoratorImport(Rule):
    """Add import for @task decorator."""

    context_providers = (Scope, ImportFinder)

    def match(self, node):
        assert (
            isinstance(node, ast.ImportFrom)
            and node.module == "airflow.operators.python"
            and any(
                alias.name in ["PythonOperator", "PythonVirtualenvOperator"]
                for alias in node.names
            )
        )
        assert not self.context["import_finder"].collect(
            "task",
            scope=self.context["scope"].resolve(node),
        )

        return AddNewImport(node, module="airflow.decorators", names=["task"])


class _AddTaskDecorator(Rule):
    """Add @task decorator for python functions to transform them into airflow tasks."""

    context_providers = (Scope, PythonCallableFinder)

    def match(self, node):
        assert isinstance(node, ast.FunctionDef)
        assert not any(
            decorator.func.id == "task"
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name)
        ) and not any(
            decorator.func.value.id == "task" and decorator.func.attr == "virtualenv"
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
        )
        assert (
            python_operator := self.context["python_callable_finder"].collect(
                node.name,
                scope=self.context["scope"].resolve(node),
            )
        )
        assert isinstance(python_operator.func, ast.Name)
        TASK_MAPPING = {
            "PythonOperator": ast.Name(id="task", ctx=ast.Load()),
            "PythonVirtualenvOperator": ast.Attribute(
                value=ast.Name(id="task", ctx=ast.Load()),
                attr="virtualenv",
                ctx=ast.Load(),
            ),
        }
        assert (decorator := TASK_MAPPING.get(python_operator.func.id))

        replacement = deepcopy(node)
        replacement.decorator_list.append(
            ast.Call(
                func=decorator,
                args=[],
                keywords=[
                    keyword
                    for keyword in python_operator.keywords
                    if keyword.arg not in ["python_callable", "op_args", "op_kwargs"]
                ],
            ),
        )
        return ReplacementAction(node, replacement)


class _ReplacePythonOperatorByFunctionCall(Rule):
    """Replace PythonOperator calls by function calls which got decorated with the @task decorator."""

    def match(self, node):
        assert (
            isinstance(node, (ast.Expr, ast.Assign))
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in ["PythonOperator", "PythonVirtualenvOperator"]
            and isinstance(node.value.func.ctx, ast.Load)
        )

        args = next(
            (
                keyword.value.elts
                for keyword in node.value.keywords
                if keyword.arg == "op_args"
            ),
            None,
        )
        kwargs = next(
            (
                keyword.value.keywords
                for keyword in node.value.keywords
                if keyword.arg == "op_kwargs" and isinstance(keyword.value, ast.Call)
            ),
            next(
                (
                    [
                        ast.keyword(arg=key.value, value=value)
                        for key, value in zip(keyword.value.keys, keyword.value.values)
                        if isinstance(key, ast.Constant)
                    ]
                    for keyword in node.value.keywords
                    if keyword.arg == "op_kwargs"
                    and isinstance(keyword.value, ast.Dict)
                ),
                None,
            ),
        )
        replacement = deepcopy(node)
        replacement.value = ast.Call(
            func=next(
                keyword.value
                for keyword in node.value.keywords
                if keyword.arg == "python_callable"
            ),
            args=[args] if args else [],
            keywords=[kwargs] if kwargs else [],
        )
        return ReplacementAction(node, replacement)


EnforceTaskFlowApi = [
    _AddTaskDecoratorImport,
    _AddTaskDecorator,
    _ReplacePythonOperatorByFunctionCall,
]
