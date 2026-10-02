from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterator


class TokenKind(enum.Enum):
    """Classe já implementada: nomes e números não devem ser alterados."""

    EOF = -1

    IDENTIFIER = 1
    INT_LITERAL = 2
    STRING_LITERAL = 3

    KW_INT = 10
    KW_BOOL = 11
    KW_VOID = 12
    KW_TRUE = 13
    KW_FALSE = 14
    KW_IF = 15
    KW_ELSE = 16
    KW_WHILE = 17
    KW_RETURN = 18
    KW_PRINT = 19

    PLUS = 20
    MINUS = 21
    STAR = 22
    SLASH = 23
    PERCENT = 24
    LESS = 25
    LESS_EQUAL = 26
    GREATER = 27
    GREATER_EQUAL = 28
    EQUAL_EQUAL = 29
    NOT_EQUAL = 30
    LOGICAL_AND = 31
    LOGICAL_OR = 32
    LOGICAL_NOT = 33
    ASSIGN = 34

    LEFT_PAREN = 40
    RIGHT_PAREN = 41
    LEFT_BRACE = 42
    RIGHT_BRACE = 43
    COMMA = 44
    SEMICOLON = 45


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    value: int | str | bool | None
    line: int
    column: int

    def __str__(self) -> str:
        return (
            f"<{self.kind.value}, {self.kind.name}, {self.lexeme!r}, "
            f"{self.value!r}, {self.line}, {self.column}>"
        )


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column

    def __str__(self) -> str:
        return f"erro léxico em {self.line}:{self.column}: {self.message}"


class Lexer:
    """Converte texto-fonte MicroC em uma sequência de tokens."""

    def __init__(self, source: str):
        self.source = source

        self.source = source
        self.pos = 0
        self.linha = 1
        self.coluna = 1


        self.keywords = {
            "int": TokenKind.KW_INT, "bool": TokenKind.KW_BOOL,
            "void": TokenKind.KW_VOID, "true": TokenKind.KW_TRUE,
            "false": TokenKind.KW_FALSE, "if": TokenKind.KW_IF,
            "else": TokenKind.KW_ELSE, "while": TokenKind.KW_WHILE,
            "return": TokenKind.KW_RETURN, "print": TokenKind.KW_PRINT
        }
    def acabou_string(self):
        return self.pos >= len(self.source)

    def verificar_caractere(self) -> str:
        if self.acabou_string():
            return ""
        return self.source[self.pos]

    def avançar(self) -> str:
        if self.acabou_string():
            return ""

        char = self.source[self.pos]
        self.pos += 1

        if char == '\n':
            self.linha += 1
            self.coluna = 1
        else:
            self.coluna += 1

        return char

    def identificador_ou_keyword(self, primeiro_caractere:str,linha: int, coluna:int) -> Token:
        lexema=primeiro_caractere
        while not self.acabou_string() and((self.verificar_caractere().isascii() and self.verificar_caractere().isalnum()) or self.verificar_caractere() == '_'):
            lexema += self.avançar()

        tipo= self.keywords.get(lexema, TokenKind.IDENTIFIER)

        valor= lexema if tipo==TokenKind.IDENTIFIER else (True if tipo == TokenKind.KW_TRUE else(False if tipo == TokenKind.KW_FALSE else None))

        return Token(tipo, lexema, valor, linha, coluna)





    def numero(self, primeiro_caractere:str,linha: int, coluna:int) -> Token:
        lexema=primeiro_caractere
        while not self.acabou_string() and self.verificar_caractere().isdigit():
            lexema += self.avançar()

        return Token(TokenKind.INT_LITERAL, lexema, int(lexema), linha, coluna)

    def _string(self,linha: int, coluna: int) -> Token:
        lexema= '"'
        caracteres_valor=[]

        while not self.acabou_string() and self.verificar_caractere() != '"':

            coluna_char= self.coluna
            char=self.avançar()
            lexema +=char

            if char == '\\':
                if not self.acabou_string():
                    proximo_caractere= self.avançar()
                    lexema += proximo_caractere

                    if proximo_caractere == 'n':
                        caracteres_valor.append('\n')
                    elif proximo_caractere  == 't':
                        caracteres_valor.append('\t')
                    elif proximo_caractere  == '"':
                        caracteres_valor.append('"')
                    elif proximo_caractere  == '"':
                        caracteres_valor.append('"')
                    elif proximo_caractere  == '\\':
                        caracteres_valor.append('\\')
                    else:
                        raise LexerError(
                            f"Sequência de escape inválida: \\{proximo_caractere}",
                            self.linha,
                            coluna_char
                        )

                else:
                    raise LexerError("String não finalizada após barra invertida", linha, coluna)
            else:
                if char == '\n':
                    raise LexerError("Quebra de linha literal não permitida em strings", self.linha - 1, coluna_char)
                caracteres_valor.append(char)
        if self.acabou_string():
            raise LexerError("String não fechada", linha, coluna)
        lexema += self.avançar()
        valor= "".join(caracteres_valor)
        return Token(TokenKind.STRING_LITERAL,lexema,valor,linha,coluna)

    def tokens(self) -> Iterator[Token]:
        """Produza todos os tokens significativos e um único EOF ao final."""

        while not self.acabou_string():
            char = self.verificar_caractere()

            if char.isspace():
                self.avançar()
                continue

            linha_começo= self.linha
            coluna_começo= self.coluna

            c= self.avançar()

            if (c.isascii() and c.isalpha()) or c== '_':
                yield self.identificador_ou_keyword(c,linha_começo,coluna_começo)
            elif c.isdigit():
                yield self.numero(c, linha_começo,coluna_começo)
            elif c== '=':
                if not self.acabou_string() and self.verificar_caractere()== '=':
                    self.avançar()
                    yield Token(TokenKind.EQUAL_EQUAL, "==",None, linha_começo, coluna_começo)
                else:
                    yield Token(TokenKind.ASSIGN , "=", None, linha_começo, coluna_começo)

            elif c == ';':
                yield Token(TokenKind.SEMICOLON, ";", None, linha_começo, coluna_começo)
            elif c == '(':
                yield Token(TokenKind.LEFT_PAREN, "(", None, linha_começo, coluna_começo)
            elif c == ')':
                yield Token(TokenKind.RIGHT_PAREN, ")", None, linha_começo, coluna_começo)
            elif c == '{':
                yield Token(TokenKind.LEFT_BRACE, "{", None, linha_começo, coluna_começo)
            elif c == '}':
                yield Token(TokenKind.RIGHT_BRACE, "}", None, linha_começo, coluna_começo)
            elif c == ',':
                yield Token(TokenKind.COMMA, ",", None, linha_começo, coluna_começo)
            elif c == '"':
                yield self._string(linha_começo,coluna_começo)
            elif c == '-':
                yield Token(TokenKind.MINUS, "-", None, linha_começo,coluna_começo)
            elif c == '+':
                yield Token(TokenKind.PLUS, "+", None, linha_começo,coluna_começo)
            elif c == '*':
                yield Token(TokenKind.STAR, "*", None, linha_começo,coluna_começo)
            elif c == '/':
                if not self.acabou_string() and self.verificar_caractere()== '/':
                    self.avançar()
                    while not self.acabou_string() and self.verificar_caractere()!= '\n':
                        self.avançar()
                    continue

                elif not self.acabou_string() and self.verificar_caractere()== '*':
                    self.avançar()
                    while not self.acabou_string():
                        char_atual= self.avançar()
                        if char_atual == '*' and not self.acabou_string() and self.verificar_caractere() == '/':
                            self.avançar()

                            break
                    else:

                        raise LexerError("Comentário de bloco não fechado", linha_começo, coluna_começo)
                    continue
                else:
                    yield Token(TokenKind.SLASH, "/", None, linha_começo,coluna_começo)

            elif c == '%':
                yield Token(TokenKind.PERCENT, "%", None, linha_começo,coluna_começo)

            elif c== '<':

                if not self.acabou_string() and self.verificar_caractere()== '=':
                    self.avançar()
                    yield Token(TokenKind.LESS_EQUAL,"<=", None, linha_começo,coluna_começo)
                else:
                    yield Token(TokenKind.LESS, "<", None, linha_começo, coluna_começo)
            elif c == '>':

                if not self.acabou_string() and self.verificar_caractere() == '=':
                    self.avançar()
                    yield Token(TokenKind.GREATER_EQUAL, ">=", None, linha_começo, coluna_começo)
                else:
                    yield Token(TokenKind.GREATER , ">", None, linha_começo, coluna_começo)

            elif c == '!':

                if not self.acabou_string() and self.verificar_caractere() == '=':
                    self.avançar()
                    yield Token(TokenKind.NOT_EQUAL, "!=", None, linha_começo, coluna_começo)
                else:
                    yield Token(TokenKind.LOGICAL_NOT , "!", None, linha_começo, coluna_começo)

            elif c == '&':

                if not self.acabou_string() and self.verificar_caractere() == '&':
                    self.avançar()
                    yield Token(TokenKind.LOGICAL_AND, "&&", None, linha_começo, coluna_começo)
                else:
                    raise LexerError(f"Caractere invalido: {c}", linha_começo, coluna_começo)
            elif c == '|':

                if not self.acabou_string() and self.verificar_caractere() == '|':
                    self.avançar()
                    yield Token(TokenKind.LOGICAL_OR, "||", None, linha_começo, coluna_começo)
                else:
                    raise LexerError(f"Caractere invalido: {c}", linha_começo, coluna_começo)

            else:
                raise  LexerError(f"Caractere invalido: {c}", linha_começo, coluna_começo)

        yield Token(TokenKind.EOF,"", None, self.linha, self.coluna)






    def scan(self) -> list[Token]:
        return list(self.tokens())