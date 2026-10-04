from semantic_errors import SemanticDiagnostic, SemanticErrorKind
from ast_nodes import TypeName
import symbols

def to_typename(t):
    if type(t).__name__ == 'TypeName': return t
    s = getattr(t, "name", getattr(t, "value", str(t)))
    if isinstance(s, str):
        s = s.lower().split('.')[-1]
        if s == "int": return TypeName.INT
        if s == "bool": return TypeName.BOOL
        if s == "void": return TypeName.VOID
    return t

class NameResolver:
    def __init__(self):
        self.diagnostics = []
        self.global_functions = {}
        self.current_scope = None

    def add_error(self, category, node):
        span = getattr(node, "span", None)
        enum_kind = SemanticErrorKind[category]
        self.diagnostics.append(
            SemanticDiagnostic(kind=enum_kind, message=enum_kind.value, span=span)
        )

    def visit(self, node):
        if node is None: return
        method_name = f'visit_{type(node).__name__}'
        if hasattr(self, method_name):
            return getattr(self, method_name)(node)
        return self.generic_visit(node)

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
            if isinstance(value, list):
                for item in value:
                    if hasattr(item, '__class__') and type(item).__name__ not in ('str', 'int', 'bool', 'float', 'NoneType'):
                        self.visit(item)
            elif hasattr(value, '__class__') and type(value).__name__ not in ('str', 'int', 'bool', 'float', 'NoneType'):
                self.visit(value)

    def visit_Program(self, node):
        funcs = getattr(node, 'functions', getattr(node, 'declarations', []))
        for decl in funcs:
            if type(decl).__name__ == "FunctionDecl":
                self.register_function(decl)
        self.check_main(node)
        # TODO: Visitar os corpos no próximo commit

    def register_function(self, node):
        name = node.name
        if name in self.global_functions:
            self.add_error("DUPLICATE_FUNCTION", node)
            return
        func_sym = symbols.FunctionSymbol(
            name=name,
            kind=symbols.SymbolKind.FUNCTION,
            type=to_typename(node.return_type),
            declaration=node,
            parameter_types=tuple(to_typename(p.type) for p in getattr(node, "parameters", []))
        )
        self.global_functions[name] = func_sym
        node.metadata["symbol"] = func_sym

    def check_main(self, node):
        main_sym = self.global_functions.get("main")
        if not main_sym or main_sym.type != TypeName.INT or len(main_sym.parameter_types) > 0:
            self.add_error("INVALID_MAIN", node)