grammar RmLang;

options {
    language = Python3;
}

program
    : (declaration | fonction | classe)* EOF
    ;

declaration
    : type ID ('=' expression)? ';'
    | 'ref' type ID '=' '&' ID ';'
    ;

type
    : 'int' | 'double' | 'float' | 'string' | 'bool' | 'void' | ID
    ;

fonction
    : 'func' type? ID '(' param_list? ')' bloc
    ;

param_list
    : param (',' param)*
    ;

param
    : type ID
    ;

classe
    : 'class' ID '{' class_member* '}'
    ;

class_member
    : declaration
    | constructeur
    | fonction_membre
    ;

constructeur
    : 'constructor' ID '(' param_list? ')' bloc
    ;

fonction_membre
    : 'func' type? ID '(' param_list? ')' bloc
    ;

bloc
    : '{' instruction* '}'
    ;

instruction
    : declaration
    | affectation
    | affectation_membre
    | method_call ';'
    | retour
    | appel_fonction ';'
    | condition
    | boucle_while
    | boucle_for
    | 'break' ';'
    | 'continue' ';'
    | print_stmt ';'
    | println_stmt ';'
    | ';'
    ;

affectation
    : ID '=' expression ';'
    ;

affectation_membre
    : objectRef '.' ID '=' expression ';'
    ;

method_call
    : objectRef '.' ID '(' argument_list? ')'
    ;

retour
    : 'return' expression? ';'
    ;

appel_fonction
    : ID '(' argument_list? ')'
    ;

condition
    : 'if' '(' expression ')' bloc ('else' 'if' '(' expression ')' bloc)* ('else' bloc)?
    ;

boucle_while
    : 'while' '(' expression ')' bloc
    ;

// ===== CORRECTION ICI =====
// for (initialisation; condition; increment)
boucle_for
    : 'for' '(' for_init? ';' expression? ';' expression? ')' bloc
    ;

for_init
    : type ID ('=' expression)?   # ForDecl
    | expression                   # ForExprInit
    ;

print_stmt
    : 'print' '(' expression ')'
    ;

println_stmt
    : 'println' '(' expression ')'
    ;

argument_list
    : expression (',' expression)*
    ;

objectRef
    : ID
    | 'this'
    ;

expression
    : objectRef '.' ID '(' argument_list? ')'   # MethodCallExpr
    | objectRef '.' ID                          # MemberAccessExpr
    | ID '(' argument_list? ')'                 # CallExpr
    | '(' expression ')'                        # ParensExpr
    | INT                                       # IntLiteral
    | FLOAT                                     # FloatLiteral
    | STRING                                    # StringLiteral
    | BOOL                                      # BoolLiteral
    | ID                                        # VarRef
    | 'null'                                    # NullLiteral
    | 'this'                                    # ThisExpr
    | '&' ID                                    # RefOfExpr
    | '*' expression                            # DerefExpr
    | '!' expression                            # NotExpr
    | '-' expression                            # UnaryMinusExpr
    | '+' expression                            # UnaryPlusExpr
    | expression '*' expression                 # MulExpr
    | expression '/' expression                 # DivExpr
    | expression '%' expression                 # ModExpr
    | expression '+' expression                 # AddExpr
    | expression '-' expression                 # SubExpr
    | expression '<' expression                 # LessExpr
    | expression '>' expression                 # GreaterExpr
    | expression '<=' expression                # LessOrEqualExpr
    | expression '>=' expression                # GreaterOrEqualExpr
    | expression '==' expression                # EqualExpr
    | expression '!=' expression                # NotEqualExpr
    | expression '&&' expression                # AndExpr
    | expression '||' expression                # OrExpr
    | <assoc=right> expression '=' expression   # AssignExpr
    ;

CLASS       : 'class';
CONSTRUCTOR : 'constructor';
FUNC        : 'func';
RETURN      : 'return';
IF          : 'if';
ELSE        : 'else';
WHILE       : 'while';
FOR         : 'for';
BREAK       : 'break';
CONTINUE    : 'continue';
PRINT       : 'print';
PRINTLN     : 'println';
REF         : 'ref';
THIS        : 'this';
NULL        : 'null';

INT_TYPE    : 'int';
DOUBLE_TYPE : 'double';
FLOAT_TYPE  : 'float';
STRING_TYPE : 'string';
BOOL_TYPE   : 'bool';
VOID_TYPE   : 'void';

BOOL
    : 'true' | 'false'
    ;

ID
    : [a-zA-Z_][a-zA-Z0-9_]*
    ;

INT
    : [0-9]+
    ;

FLOAT
    : [0-9]+ '.' [0-9]+
    ;

STRING
    : '"' (~["\r\n])* '"'
    ;



COMMENT_SINGLE
    : '//' ~[\r\n]* -> skip
    ;

COMMENT_MULTI
    : '/*' .*? '*/' -> skip
    ;

WS
    : [ \r\n\t]+ -> skip
    ;

UNKNOWN
    : .
    ;