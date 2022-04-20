import ast
from typing import Optional

from refactor import Representative
from refactor.context import ScopeInfo


class ImportFinder(Representative):
    """Find import by alias name."""

    def collect(self, name: str, scope: ScopeInfo) -> Optional[ast.ImportFrom]:
        return next(
            (
                node
                for node in ast.walk(self.context.tree)
                if isinstance(node, ast.ImportFrom)
                and any(alias.name == name for alias in node.names)
                and scope.can_reach(self.context["scope"].resolve(node))
            ),
            None,
        )


class PythonCallableFinder(Representative):
    """Find python callables references in PythonOperator."""

    def collect(self, name: str, scope: ScopeInfo) -> Optional[ast.Call]:
        return next(
            (
                node
                for node in ast.walk(self.context.tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ["PythonOperator", "PythonVirtualenvOperator"]
                and any(
                    keyword.arg == "python_callable"
                    and isinstance(keyword.value, ast.Name)
                    and keyword.value.id == name
                    for keyword in node.keywords
                )
                and scope.can_reach(self.context["scope"].resolve(node))
            ),
            None,
        )
