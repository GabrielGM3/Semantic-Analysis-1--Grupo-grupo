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
    def __init__(self):
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

        # Garante que o dicionário metadata existe no nó
        if not hasattr(node, "metadata"):
            node.metadata = {}

        method_name = f'visit_{type(node).__name__}'

        result = None
        if hasattr(self, method_name):
            result = getattr(self, method_name)(node)
        else:
            result = self.generic_visit(node)

        # CONTRATO DE METADADOS TOTAL: Garante a chave 'type' em todos os nós visitados
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
            # Suporte alargado para listas e tuplos
            if isinstance(value, (list, tuple)):
                for item in value:
                    if hasattr(item, '__class__') and type(item).__name__ not in ('str', 'int', 'bool', 'float',
                                                                                  'NoneType'):
                        self.visit(item)
            elif hasattr(value, '__class__') and type(value).__name__ not in ('str', 'int', 'bool', 'float',
                                                                              'NoneType'):
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

    def visit_UnaryExpr(self, node):
        self.expr_context_stack.append(True)
        operand_type = self.visit(node.operand)
        self.expr_context_stack.pop()

        if operand_type == TypeUnknown:
            return TypeUnknown

        op = getattr(node, "operator", getattr(node, "op", None))

        if op is not None and not isinstance(op, str):
            op = getattr(op, "value", getattr(op, "name", str(op)))

        if op == "-":
            if operand_type != TypeName.INT:
                self.add_error("INVALID_UNARY_OPERAND", node)
                return TypeUnknown
            node.metadata["type"] = TypeName.INT
            return TypeName.INT
        elif op == "!":
            if operand_type != TypeName.BOOL:
                self.add_error("INVALID_UNARY_OPERAND", node)
                return TypeUnknown
            node.metadata["type"] = TypeName.BOOL
            return TypeName.BOOL
        return TypeUnknown

    def visit_BinaryExpr(self, node):
        self.expr_context_stack.append(True)
        left_t = self.visit(node.left)
        right_t = self.visit(node.right)
        self.expr_context_stack.pop()

        if left_t == TypeUnknown or right_t == TypeUnknown:
            return TypeUnknown

        op = getattr(node, "operator", getattr(node, "op", None))

        if op is not None and not isinstance(op, str):
            op = getattr(op, "value", getattr(op, "name", str(op)))

        if op in ("+", "-", "*", "/", "%"):
            if left_t == TypeName.INT and right_t == TypeName.INT:
                node.metadata["type"] = TypeName.INT
                return TypeName.INT
        elif op in ("<", "<=", ">", ">="):
            if left_t == TypeName.INT and right_t == TypeName.INT:
                node.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL
        elif op in ("==", "!="):
            if (left_t == TypeName.INT and right_t == TypeName.INT) or \
                    (left_t == TypeName.BOOL and right_t == TypeName.BOOL):
                node.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL
        elif op in ("&&", "||"):
            if left_t == TypeName.BOOL and right_t == TypeName.BOOL:
                node.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL

        self.add_error("INVALID_BINARY_OPERANDS", node)
        return TypeUnknown

    def visit_CallExpr(self, node):
        self.expr_context_stack.append(True)
        # O SEGREDO ESTAVA AQUI: O parser.py define os argumentos como 'args'
        call_args = getattr(node, "args", getattr(node, "arguments", []))
        arg_types = [self.visit(arg) for arg in call_args]
        self.expr_context_stack.pop()

        if "symbol" not in node.metadata:
            return TypeUnknown

        func_sym = node.metadata["symbol"]
        ret_type = to_typename(func_sym.type)

        if len(arg_types) != len(func_sym.parameter_types):
            self.add_error("ARITY_MISMATCH", node)

        for i, (arg_t, param_t) in enumerate(zip(arg_types, func_sym.parameter_types)):
            expected_t = to_typename(param_t)
            if arg_t != TypeUnknown and arg_t != expected_t:
                self.add_error("ARGUMENT_TYPE_MISMATCH", call_args[i])

        if ret_type == TypeName.VOID:
            if self.expr_context_stack[-1] == True:
                self.add_error("VOID_VALUE_USED", node)
                return TypeUnknown
            node.metadata["type"] = TypeName.VOID
            return TypeName.VOID

        node.metadata["type"] = ret_type
        return ret_type

    def visit_Assignment(self, node):
        self.expr_context_stack.append(True)
        var_type = self.visit(node.target)
        val_type = self.visit(node.value)
        self.expr_context_stack.pop()

        if var_type != TypeUnknown and val_type != TypeUnknown:
            if var_type != val_type:
                self.add_error("ASSIGNMENT_TYPE_MISMATCH", node.value)
            else:
                node.metadata["type"] = var_type
                return var_type

        return TypeUnknown

    def visit_IfStmt(self, node):
        self.expr_context_stack.append(True)
        cond_t = self.visit(node.condition)
        self.expr_context_stack.pop()

        if cond_t != TypeUnknown and cond_t != TypeName.BOOL:
            self.add_error("CONDITION_TYPE_MISMATCH", node.condition)

        self.expr_context_stack.append(False)
        if hasattr(node, "then_block"):
            self.visit(node.then_block)
        elif hasattr(node, "then_stmt"):
            self.visit(node.then_stmt)
        elif hasattr(node, "then_branch"):
            self.visit(node.then_branch)
        elif hasattr(node, "body"):
            self.visit(node.body)

        if hasattr(node, "else_block"):
            self.visit(node.else_block)
        elif hasattr(node, "else_stmt"):
            self.visit(node.else_stmt)
        elif hasattr(node, "else_branch"):
            self.visit(node.else_branch)
        self.expr_context_stack.pop()

    def visit_WhileStmt(self, node):
        self.expr_context_stack.append(True)
        cond_t = self.visit(node.condition)
        self.expr_context_stack.pop()

        if cond_t != TypeUnknown and cond_t != TypeName.BOOL:
            self.add_error("CONDITION_TYPE_MISMATCH", node.condition)

        self.expr_context_stack.append(False)
        if hasattr(node, "body"):
            self.visit(node.body)
        elif hasattr(node, "stmt"):
            self.visit(node.stmt)
        elif hasattr(node, "block"):
            self.visit(node.block)
        self.expr_context_stack.pop()

    def visit_ReturnStmt(self, node):
        curr_ret = self.current_function_return_type
        val_node = getattr(node, "value", None)

        if val_node:
            self.expr_context_stack.append(True)
            ret_t = self.visit(val_node)
            self.expr_context_stack.pop()

            if curr_ret == TypeName.VOID:
                self.add_error("RETURN_MISMATCH", val_node)
            elif ret_t != TypeUnknown and ret_t != curr_ret:
                self.add_error("RETURN_MISMATCH", val_node)
        else:
            if curr_ret != TypeName.VOID:
                self.add_error("RETURN_MISMATCH", node)

    def visit_CallStmt(self, node):
        self.expr_context_stack.append(False)
        if hasattr(node, "call_expr"):
            self.visit(node.call_expr)
        elif hasattr(node, "expression"):
            self.visit(node.expression)
        else:
            self.generic_visit(node)
        self.expr_context_stack.pop()

    def visit_ExprStmt(self, node):
        self.expr_context_stack.append(False)
        self.visit(node.expression)
        self.expr_context_stack.pop()

    def visit_PrintStmt(self, node):
        self.expr_context_stack.append(True)

        items = getattr(node, "items", getattr(node, "arguments", getattr(node, "expression", [])))
        if not isinstance(items, list):
            items = [items]

        for item in items:
            self.visit(item)

        self.expr_context_stack.pop()


def check_types(program: Program) -> None:
    """Determine tipos de expressões e valide seus contextos."""

    # 1. Use os símbolos anexados pela resolução de nomes.
    # 2. Determine cada expressão de baixo para cima.
    # 3. Valide operadores, chamadas, comandos e declarações.
    # 4. Anote expressões válidas e acumule os diagnósticos da passagem.

    checker = TypeChecker()
    checker.visit(program)

    # Acumulando os diagnósticos no nó program (caso a arquitetura do compilador os colete dali)
    if not hasattr(program, "diagnostics"):
        program.diagnostics = []

    program.diagnostics.extend(checker.diagnostics)