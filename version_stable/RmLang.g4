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
    | type ID '[' expression ']' ('=' array_init)? ';'   // Tableau
    ;

array_init
    : '{' expression (',' expression)* '}'   // Initialisation de tableau
    ;

type
    : 'char' | 'int' | 'double' | 'float' | 'string' | 'bool' | 'void' | ID
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
    | affectation_composee           // +=, -=, &=, |=, etc.
    | affectation
    | affectation_membre_tableau
    | affectation_membre
    | affectation_tableau
    | method_call ';'
    | retour
    | appel_fonction ';'
    | input_stmt 
    | condition
    | boucle_while
    | boucle_for
    | 'break' ';'
    | 'continue' ';'
    | print_stmt ';'
    | println_stmt ';'
    | ';'
    ;

affectation_composee
    : ID COMPOUND_ASSIGN expression ';'                    # SimpleCompoundAssign
    | ID '[' expression ']' COMPOUND_ASSIGN expression ';' # ArrayCompoundAssign
    ;

affectation
    : ID '=' expression ';'
    ;

affectation_membre
    : objectRef '.' ID '=' expression ';'
    ;

affectation_tableau
    : ID '[' expression ']' '=' expression ';'
    ;

affectation_membre_tableau
    : objectRef '.' ID '[' expression ']' '=' expression ';'
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

input_stmt
    : 'input' '(' input_type? ')' ';'
    | 'input' '(' ')' ';'
    ;

argument_list
    : expression (',' expression)*
    ;

input_type
    : 'int'
    | 'double'
    | 'float'
    | 'string'
    | 'bool'
    ;

objectRef
    : ID
    | 'this'
    ;

expression
    : objectRef '.' ID '[' expression ']'                 # MemberArrayAccessExpr
    | objectRef '.' ID '(' argument_list? ')'             # MethodCallExpr
    | objectRef '.' ID                                    # MemberAccessExpr
    | 'input' '(' input_type? ')'                         # InputExpr
    | ID '[' expression ']'                               # ArrayAccessExpr
    | ID '(' argument_list? ')'                           # CallExpr
    | '(' expression ')'                                  # ParensExpr
    | INT                                                 # IntLiteral
    | FLOAT                                               # FloatLiteral
    | STRING                                              # StringLiteral
    | BOOL                                                # BoolLiteral
    | CHAR                                                # CharLiteral
    | ID                                                  # VarRef
    | 'null'                                              # NullLiteral
    | 'this'                                              # ThisExpr
    | '&' ID                                              # RefOfExpr
    | '*' expression                                      # DerefExpr
    | '!' expression                                      # NotExpr
    | '~' expression                                      # BitwiseNotExpr    // NOUVEAU
    | '-' expression                                      # UnaryMinusExpr
    | '+' expression                                      # UnaryPlusExpr
    | <assoc=right> expression '=' expression             # AssignExpr
    | expression COMPOUND_ASSIGN expression               # CompoundAssignExpr // NOUVEAU
    | expression '*' expression                           # MulExpr
    | expression '/' expression                           # DivExpr
    | expression '%' expression                           # ModExpr
    | expression '+' expression                           # AddExpr
    | expression '-' expression                           # SubExpr
    | expression '<<' expression                          # LeftShiftExpr     // NOUVEAU
    | expression '>>' expression                          # RightShiftExpr    // NOUVEAU
    | expression '<' expression                           # LessExpr
    | expression '>' expression                           # GreaterExpr
    | expression '<=' expression                          # LessOrEqualExpr
    | expression '>=' expression                          # GreaterOrEqualExpr
    | expression '==' expression                          # EqualExpr
    | expression '!=' expression                          # NotEqualExpr
    | expression '&' expression                           # BitwiseAndExpr    // NOUVEAU
    | expression '^' expression                           # BitwiseXorExpr    // NOUVEAU
    | expression '|' expression                           # BitwiseOrExpr     // NOUVEAU
    | expression '&&' expression                          # AndExpr
    | expression '||' expression                          # OrExpr
    | '[' expression (',' expression)* ']'                # ArrayLiteral
    ;

// ===== NOUVEAUX TOKENS =====

// Opérateurs d'affectation composée (avec opérateurs binaires)
COMPOUND_ASSIGN
    : '+='
    | '-='
    | '*='
    | '/='
    | '%='
    | '&='
    | '|='
    | '^='
    | '<<='
    | '>>='
    ;

// ===== MOTS-CLÉS =====

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
INPUT       : 'input';
REF         : 'ref';
THIS        : 'this';
NULL        : 'null';

CHAR_TYPE   : 'char';
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

CHAR : '\'' ( ~['\\] | '\\' . ) '\'' ;

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