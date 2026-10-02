from __future__ import annotations

from collections.abc import Sequence

from Lexer import Token, TokenKind
from ast_nodes import (
    Block, Expr, FunctionDecl, Node, Parameter, PrintItem, Program,
    SourceSpan, Stmt, StringLiteral, TypeName, Assignment, CallExpr,
    VarDecl, IfStmt, BinaryOperator, UnaryOperator, UnaryExpr, IdentifierExpr,
    BinaryExpr, IntLiteral, PrintStmt, BoolLiteral, CallStmt, WhileStmt,
    ReturnStmt,
)

TYPE_START = {TokenKind.KW_INT, TokenKind.KW_BOOL, TokenKind.KW_VOID}
EXPRESSION_START = {
    TokenKind.IDENTIFIER, TokenKind.INT_LITERAL, TokenKind.KW_FALSE,
    TokenKind.KW_TRUE, TokenKind.LEFT_PAREN, TokenKind.LOGICAL_NOT,
    TokenKind.MINUS,
}
STATEMENT_START = TYPE_START | {
    TokenKind.IDENTIFIER, TokenKind.KW_IF, TokenKind.KW_WHILE,
    TokenKind.KW_RETURN, TokenKind.KW_PRINT, TokenKind.LEFT_BRACE,
}

TYPE_BY_TOKEN = {
    TokenKind.KW_INT: TypeName.INT,
    TokenKind.KW_BOOL: TypeName.BOOL,
    TokenKind.KW_VOID: TypeName.VOID,
}

class ParserError(Exception):
    def __init__(self, token: Token, expected: set[TokenKind]):
        self.token = token
        self.expected = frozenset(expected)
        super().__init__()

    @property
    def line(self) -> int:
        return self.token.line

    @property
    def column(self) -> int:
        return self.token.column

    def __str__(self) -> str:
        names = ", ".join(kind.name for kind in sorted(
            self.expected,
            key=lambda kind: kind.value,
        ))
        return (
            f"erro sintático em {self.line}:{self.column}: esperado {{{names}}}, "
            f"encontrado {self.token.kind.name} ({self.token.lexeme!r})"
        )

class Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        if not self.tokens:
            raise ValueError("a sequência de tokens deve terminar em EOF")
        if self.tokens[-1].kind is not TokenKind.EOF:
            raise ValueError("o último token deve ser EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise ValueError("EOF deve aparecer uma única vez, no final")
        self.current = 0

    def peek(self, offset: int = 0) -> Token:
        index = min(self.current + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def check(self, kind: TokenKind) -> bool:
        return self.peek().kind is kind

    def advance(self) -> Token:
        token = self.peek()
        if self.current < len(self.tokens) - 1:
            self.current += 1
        return token

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.peek().kind in kinds:
            return self.advance()
        return None

    def expect(self, kinds: TokenKind | set[TokenKind]) -> Token:
        expected = kinds if isinstance(kinds, set) else {kinds}
        token = self.peek()
        if token.kind not in expected:
            raise ParserError(token, set(expected))
        return self.advance()

    @staticmethod
    def _token_span(token: Token) -> SourceSpan:
        return SourceSpan(
            token.line, token.column, token.line, token.column + len(token.lexeme),
        )

    @staticmethod
    def _start(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.start_line, value.span.start_column
        return value.line, value.column

    @staticmethod
    def _end(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.end_line, value.span.end_column
        return value.line, value.column + len(value.lexeme)

    @classmethod
    def _span(cls, first: Token | Node, last: Token | Node) -> SourceSpan:
        start_line, start_column = cls._start(first)
        end_line, end_column = cls._end(last)
        return SourceSpan(start_line, start_column, end_line, end_column)

    def parse(self) -> Program:
        return self.parse_program()

    def parse_program(self) -> Program:
        start = self.peek()
        functions: list[FunctionDecl] = []
        while self.peek().kind in TYPE_START:
            functions.append(self.parse_function())
        eof = self.expect(TokenKind.EOF)
        return Program(functions, span=self._span(start, eof))

    def parse_function(self) -> FunctionDecl:
        start = self.peek()
        return_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        self.expect(TokenKind.LEFT_PAREN)
        parameters = (
            self.parse_parameter_list()
            if self.peek().kind in TYPE_START
            else []
        )
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return FunctionDecl(
            return_type, name.lexeme, parameters, body, span=self._span(start, body),
        )

    def parse_type(self) -> TypeName:
        token = self.expect(TYPE_START)
        return TYPE_BY_TOKEN[token.kind]

    def parse_parameter_list(self) -> list[Parameter]:
        parameters = [self.parse_parameter()]
        while self.match(TokenKind.COMMA):
            parameters.append(self.parse_parameter())
        return parameters

    def parse_parameter(self) -> Parameter:
        start = self.peek()
        param_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        return Parameter(
            param_type,
            name.lexeme,
            span=self._span(start, name),
        )

    def parse_block(self) -> Block:
        start = self.expect(TokenKind.LEFT_BRACE)
        statements = []
        while not self.check(TokenKind.RIGHT_BRACE):
            statements.append(self.parse_statement())
        end = self.expect(TokenKind.RIGHT_BRACE)
        return Block(statements, span=self._span(start, end))

    def parse_statement(self) -> Stmt:
        if self.check(TokenKind.LEFT_BRACE):
            return self.parse_block()
        if self.peek().kind in TYPE_START:
            return self.parse_declaration()
        if self.check(TokenKind.KW_IF):
            return self.parse_if_statement()
        if self.check(TokenKind.KW_WHILE):
            return self.parse_while_statement()
        if self.check(TokenKind.KW_RETURN):
            return self.parse_return_statement()
        if self.check(TokenKind.KW_PRINT):
            return self.parse_print_statement()
        if self.check(TokenKind.IDENTIFIER):
            return self.parse_id_or_call_statement()

        raise ParserError(self.peek(), STATEMENT_START)

    def parse_id_or_call_statement(self) -> Stmt:
        start = self.expect(TokenKind.IDENTIFIER)

        if self.match(TokenKind.ASSIGN):
            value = self.parse_expression()
            end = self.expect(TokenKind.SEMICOLON)
            target = IdentifierExpr(start.lexeme, span=self._span(start, end))
            return Assignment(target, value, span=self._span(start, end))
        elif self.match(TokenKind.LEFT_PAREN):
            args = self.parse_arguments()
            right_paren = self.expect(TokenKind.RIGHT_PAREN)
            end = self.expect(TokenKind.SEMICOLON)
            call_expr = CallExpr(start.lexeme, args, span=self._span(start, right_paren))
            return CallStmt(call_expr, span=self._span(start, end))

        raise ParserError(self.peek(), {TokenKind.ASSIGN, TokenKind.LEFT_PAREN})

    def parse_declaration(self) -> Stmt:
        start = self.peek()
        var_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)

        initializer = None
        if self.match(TokenKind.ASSIGN):
            initializer = self.parse_expression()

        end = self.expect(TokenKind.SEMICOLON)
        return VarDecl(var_type, name.lexeme, initializer, span=self._span(start, end))

    def parse_if_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_IF)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        then_block = self.parse_block()

        else_block = None
        end = then_block

        if self.match(TokenKind.KW_ELSE):
            else_block = self.parse_block()
            end = else_block

        return IfStmt(condition, then_block, else_block, span=self._span(start, end))

    def parse_while_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_WHILE)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()

        return WhileStmt(condition, body, span=self._span(start, body))

    def parse_return_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_RETURN)
        value = None
        if not self.check(TokenKind.SEMICOLON):
            value = self.parse_expression()

        end = self.expect(TokenKind.SEMICOLON)

        return ReturnStmt(value, span=self._span(start, end))

    def parse_print_statement(self) -> Stmt:

        start = self.expect(TokenKind.KW_PRINT)
        self.expect(TokenKind.LEFT_PAREN)
        items = [self.parse_print_item()]
        while self.match(TokenKind.COMMA):
            items.append(self.parse_print_item())
        self.expect(TokenKind.RIGHT_PAREN)
        end = self.expect(TokenKind.SEMICOLON)
        return PrintStmt(items, span=self._span(start, end))

    def parse_print_item(self) -> PrintItem:
        if self.check(TokenKind.STRING_LITERAL):
            return self.parse_string_literals()
        return self.parse_expression()

    def parse_string_literals(self) -> StringLiteral:
        start = self.expect(TokenKind.STRING_LITERAL)
        value = start.lexeme[1:-1]
        end = start

        while self.check(TokenKind.STRING_LITERAL):
            token = self.advance()
            value += token.lexeme[1:-1]
            end = token

        return StringLiteral(value, span=self._span(start, end))

    def parse_expression(self) -> Expr:
        return self.parse_logical_or()

    def parse_logical_or(self) -> Expr:
        expr = self.parse_logical_and()
        while self.match(TokenKind.LOGICAL_OR):
            right = self.parse_logical_and()
            expr = BinaryExpr(BinaryOperator.LOGICAL_OR, expr, right, span=self._span(expr, right))

        return expr

    def parse_logical_and(self) -> Expr:
        expr = self.parse_equality()
        while self.match(TokenKind.LOGICAL_AND):
            right = self.parse_logical_equality()
            expr = BinaryExpr(BinaryOperator.LOGICAL_AND, expr, right, span=self._span(expr, right))

        return expr

    def parse_equality(self) -> Expr:
        expr = self.parse_relational()
        while True:
            op_token = self.match(TokenKind.EQUAL_EQUAL, TokenKind.NOT_EQUAL)
            if not op_token:
                break
            op = BinaryOperator.EQUAL if op_token.kind == TokenKind.EQUAL_EQUAL else BinaryOperator.NOT_EQUAL
            right = self.parse_relational()
            expr = BinaryExpr(op, expr, right, span=self._span(expr, right))

        return expr

    def parse_relational(self) -> Expr:
        expr = self.parse_additive()
        while True:
            op_token = self.match(TokenKind.LESS, TokenKind.LESS_EQUAL, TokenKind.GREATER, TokenKind.GREATER_EQUAL)
            if not op_token:
                break
            op_map = {
                TokenKind.LESS: BinaryOperator.LESS,
                TokenKind.GREATER: BinaryOperator.GREATER,
                TokenKind.LESS_EQUAL: BinaryOperator.LESS_EQUAL,
                TokenKind.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL

            }
            right = self.parse_additive()
            expr = BinaryExpr(op_map[op_token.kind], expr, right, span=self._span(expr, right))
        return expr

    def parse_additive(self) -> Expr:
        expr = self.parse_multiplicative()
        while True:
            op_token = self.match(TokenKind.PLUS, TokenKind.MINUS)
            if not op_token:
                break
            op = BinaryOperator.ADD if op_token.kind == TokenKind.PLUS else BinaryOperator.SUBTRACT
            right = self.parse_multiplicative()
            expr = BinaryExpr(op, expr, right, span=self._span(expr, right))

        return expr

    def parse_multiplicative(self) -> Expr:
        expr = self.parse_unary()
        while True:
            op_token = self.match(TokenKind.STAR, TokenKind.SLASH, TokenKind.PERCENT)
            if not op_token:
                break
            op_map = {
                TokenKind.STAR: BinaryOperator.MULTIPLY,
                TokenKind.SLASH: BinaryOperator.DIVIDE,
                TokenKind.PERCENT: BinaryOperator.REMAINDER

            }
            right = self.parse_unary()
            expr = BinaryExpr(op_map[op_token.kind], expr, right, span=self._span(expr, right))
        return expr

    def parse_unary(self) -> Expr:
        op_token = self.match(TokenKind.MINUS, TokenKind.LOGICAL_NOT)
        if op_token:
            op = UnaryOperator.NEGATE if op_token.kind == TokenKind.MINUS else UnaryOperator.NOT
            operand = self.parse_unary()
            return UnaryExpr(op, operand, span=self._span(op_token, operand))
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        token = self.advance()

        if token.kind == TokenKind.INT_LITERAL:
            return IntLiteral(int(token.lexeme), span=self._token_span(token))

        if token.kind in (TokenKind.KW_TRUE, TokenKind.KW_FALSE):
            if token.kind == TokenKind.KW_TRUE:
                return BoolLiteral(True, span=self._token_span(token))
            else:
                return BoolLiteral(False, span=self._token_span(token))

        if token.kind == TokenKind.IDENTIFIER:
            if self.match(TokenKind.LEFT_PAREN):
                args = self.parse_arguments()
                right_paren = self.expect(TokenKind.RIGHT_PAREN)
                return CallExpr(token.lexeme, args, span=self._span(token, right_paren))
            return IdentifierExpr(token.lexeme, span=self._token_span(token))
        if token.kind == TokenKind.LEFT_PAREN:
            expr = self.parse_expression()
            end = self.expect(TokenKind.RIGHT_PAREN)

            expr.span = self._span(token, end)
            return expr
        raise ParserError(token, EXPRESSION_START)

    def parse_arguments(self) -> list[Expr]:
        args = []
        if self.peek().kind in EXPRESSION_START:
            args.append(self.parse_expression())
            while self.match(TokenKind.COMMA):
                args.append(self.parse_expression())
        return args