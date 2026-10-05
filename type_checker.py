from __future__ import annotations

from ast_nodes import Program, TypeName
from semantic_errors import SemanticDiagnostic, SemanticErrorKind


class TypeUnknown:
    pass


def to_typename(t):
    if t is None or t == TypeUnknown or type(t).__name__ == "TypeUnknown":
        return TypeUnknown
    if type(t).__name__ == 'TypeName':
        return t
    s = getattr(t, "name", getattr(t, "value", str(t)))
    if isinstance(s, str):
        s = s.lower().split('.')[-1]
        if s == "int": return TypeName.INT
        if s == "bool": return TypeName.BOOL
        if s == "void": return TypeName.VOID
    return TypeUnknown


class TypeChecker:
    def _init_(self):
        self.diagnostics = []
        self.current_function_return_type = None
        self.expr_context_stack = [False]

    def add_error(self, category, node):
        span = getattr(node, "span", None)
        enum_kind = SemanticErrorKind[category]
        self.diagnostics.append(
            SemanticDiagnostic(kind=enum_kind, message=enum_kind.value, span=span)
        )

    def visit(self, node):
        if node is None:
            return None


        if not hasattr(node, "metadata"):
            node.metadata = {}

        method_name = f'visit_{type(node).__name__}'

        result = None
        if hasattr(self, method_name):
            result = getattr(self, method_name)(node)
        else:
            result = self.generic_visit(node)


        if "type" not in node.metadata:
            node.metadata["type"] = result if result is not None else TypeUnknown

        return result

    def generic_visit(self, node):
        if not hasattr(self, '_visited_nodes'):
            self._visited_nodes = set()
        node_id = id(node)
        if node_id in self._visited_nodes: return
        self._visited_nodes.add(node_id)

        if hasattr(node, '__dataclass_fields__'):
            keys = node.__dataclass_fields__.keys()
        elif hasattr(node, '__slots__'):
            keys = node.__slots__
            if isinstance(keys, str): keys = [keys]
        elif hasattr(node, '__dict__'):
            keys = node.__dict__.keys()
        else:
            keys = [k for k in dir(node) if not k.startswith('_') and not callable(getattr(node, k))]

        for key in keys:
            if key in ('span', 'metadata', 'parent', 'scope', 'symbol', 'symbols'):
                continue
            value = getattr(node, key, None)

            if isinstance(value, (list, tuple)):
                for item in value:
                    if hasattr(item, '_class') and type(item).name_ not in ('str', 'int', 'bool', 'float',
                                                                            'NoneType'):
                        self.visit(item)
            elif hasattr(value, '_class') and type(value).name_ not in ('str', 'int', 'bool', 'float',
                                                                        'NoneType'):
                self.visit(value)


def check_types(program: Program) -> None:
    """Determine tipos de expressões e valide seus contextos."""
    checker = TypeChecker()
    checker.visit(program)


    if not hasattr(program, "diagnostics"):
        program.diagnostics = []

    program.diagnostics.extend(checker.diagnostics)