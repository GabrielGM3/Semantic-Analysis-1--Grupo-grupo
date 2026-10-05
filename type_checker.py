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
                    if hasattr(item, '__class__') and type(item).name_ not in ('str', 'int', 'bool', 'float', 'NoneType'):
                        self.visit(item)
            elif hasattr(value, '__class__') and type(value).name_ not in ('str', 'int', 'bool', 'float', 'NoneType'):
                self.visit(value)

    def visit_Program(self, node):
        funcs = getattr(node, 'functions', getattr(node, 'declarations', []))
        for decl in funcs:
            self.expr_context_stack.append(False)
            self.visit(decl)
            self.expr_context_stack.pop()

    def visit_FunctionDecl(self, node):
        self.current_function_return_type = to_typename(node.return_type)
        node.metadata["type"] = self.current_function_return_type

        for param in getattr(node, "parameters", []):
            self.visit(param)
        if getattr(node, "body", None):
            self.expr_context_stack.append(False)
            self.visit(node.body)
            self.expr_context_stack.pop()
        self.current_function_return_type = None

    def visit_Block(self, node):
        self.expr_context_stack.append(False)
        for stmt in getattr(node, "statements", []):
            self.visit(stmt)
        self.expr_context_stack.pop()

    def visit_Parameter(self, node):
        t = getattr(node, "type", getattr(node, "param_type", None))
        param_t = to_typename(t)
        node.metadata["type"] = param_t

        if param_t == TypeName.VOID:
            self.add_error("VOID_PARAMETER", node)

    def visit_VarDecl(self, node):
        t = getattr(node, "type", getattr(node, "var_type", None))
        decl_type = to_typename(t)
        node.metadata["type"] = decl_type

        if decl_type == TypeName.VOID:
            self.add_error("VOID_VARIABLE", node)
            decl_type = TypeUnknown

        if getattr(node, "initializer", None):
            self.expr_context_stack.append(True)
            init_type = self.visit(node.initializer)
            self.expr_context_stack.pop()

            if init_type != TypeUnknown and decl_type != TypeUnknown and init_type != decl_type:
                self.add_error("INITIALIZER_TYPE_MISMATCH", node.initializer)

    def visit_IntLiteral(self, node):
        val = getattr(node, "value", 0)
        if not (0 <= val <= 2147483647):
            self.add_error("INTEGER_LITERAL_OUT_OF_RANGE", node)
            return TypeUnknown
        node.metadata["type"] = TypeName.INT
        return TypeName.INT

    def visit_IntegerLiteral(self, node):
        return self.visit_IntLiteral(node)

    def visit_BoolLiteral(self, node):
        node.metadata["type"] = TypeName.BOOL
        return TypeName.BOOL

    def visit_BooleanLiteral(self, node):
        return self.visit_BoolLiteral(node)

    def visit_StringLiteral(self, node):
        node.metadata["type"] = TypeUnknown
        return TypeUnknown

    def visit_IdentifierExpr(self, node):
        if "symbol" in node.metadata:
            t = to_typename(node.metadata["symbol"].type)
            node.metadata["type"] = t
            return t
        return TypeUnknown


def check_types(program: Program) -> None:
    checker = TypeChecker()
    checker.visit(program)
    if not hasattr(program, "diagnostics"):
        program.diagnostics = []
    program.diagnostics.extend(checker.diagnostics)