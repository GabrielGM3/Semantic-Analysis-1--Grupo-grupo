from name_resolver import NameResolver
from type_checker import TypeChecker
from semantic_errors import SemanticError

class SemanticAnalyzer:
    def analyze(self, program):
        #Resolução de Nomes
        resolver = NameResolver()
        resolver.visit(program)

        if resolver.diagnostics:
            raise SemanticError(diagnostics=tuple(resolver.diagnostics))

        #Verificação de Tipos
        checker = TypeChecker()
        checker.visit(program)

        if checker.diagnostics:
            raise SemanticError(diagnostics=tuple(checker.diagnostics))

        return program